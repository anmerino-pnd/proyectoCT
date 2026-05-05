import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import SecretStr
from pymongo.errors import PyMongoError
from langchain_openai import ChatOpenAI
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING, ASCENDING, UpdateOne
from bson import ObjectId

from ct.settings.config import EVAL_OUTPUT_DIR, EVAL_STATE_FILE
from ct.evaluation.metrics.faithfulness import evaluate_faithfulness
from ct.evaluation.metrics.context_recall import evaluate_context_recall
from ct.evaluation.metrics.answer_relevancy import evaluate_answer_relevancy
from ct.evaluation.metrics.context_precision import evaluate_context_precision
from ct.evaluation.schemas import (
    EvaluationInput,
    EvaluationResult,
    MetricScore,
    EvaluationState,
    WindowEntry,
)
from ct.settings.clients import (
    mongo_uri,
    mongo_collection_message_backup,
    openai_api_key,
)

logger = logging.getLogger(__name__)

METRIC_WEIGHTS = {
    "faithfulness":      0.40,
    "answer_relevancy":  0.35,
    "context_precision": 0.125,
    "context_recall":    0.125,
}

WINDOW_SIZE = 10  # documentos por ventana


class RAGASEvaluator:
    def __init__(
        self,
        evaluator_model: str = "gpt-4o-mini",
        n_last: int = 10,
        eval_collection: str = "evaluation_results",
        output_dir: Path = EVAL_OUTPUT_DIR,
        state_file: Optional[Path] = None,
    ):
        self.evaluator_model = evaluator_model
        self.n_last = n_last
        self.output_dir = output_dir
        self.state_file = state_file or EVAL_STATE_FILE

        self.llm = ChatOpenAI(
            model=self.evaluator_model,
            temperature=0,
            api_key=SecretStr(openai_api_key),
        )

        # MongoDB — solo lectura garantizada, escritura opcional
        self.client = MongoClient(mongo_uri).get_default_database()
        self.message_backup = self.client[mongo_collection_message_backup]

        self._mongo_write_available = False
        try:
            self.eval_collection = self.client[eval_collection]
            self.eval_collection.find_one({})
            self._mongo_write_available = True
            logger.info("✅ MongoDB eval collection disponible para escritura.")
        except PyMongoError as e:
            logger.warning(
                f"⚠️ Sin permisos en MongoDB eval collection: {e}\n"
                f"   → Los resultados se guardarán solo en JSON ({self.output_dir})"
            )
            self.eval_collection = None

        # Cargar estado persistente del evaluador
        self.state: EvaluationState = self._load_state()
    # ================================================================== #
    # RAGAS WINDOW STATE / FETCH / FLAGS                                  #
    # ================================================================== #

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _set_last_error(self, message: str):
        """Guarda último error en eval_state.json para mostrarlo en UI."""
        self.state.last_error = str(message)
        self.state.last_error_at = self._now_utc()
        self._save_state()

    def _clear_last_error(self):
        """Limpia último error persistido."""
        self.state.last_error = None
        self.state.last_error_at = None

    def _build_window_id(self, batch_type: str) -> str:
        """ID legible para asociar docs evaluados a una ventana."""
        ts = self._now_utc().strftime("%Y%m%d_%H%M%S")
        return f"ragas_{batch_type}_{ts}"

    def fetch_latest_bootstrap_messages(self, n: int = WINDOW_SIZE) -> list[EvaluationInput]:
        """
        Bootstrap inicial:
        toma los últimos N documentos relevantes actuales.
        
        Nota:
        - No usamos ragas_evaluated aquí.
        - No marcamos los anteriores.
        - Los anteriores se ignorarán mediante ragas_bootstrap_at.
        """
        try:
            docs = list(
                self.message_backup
                .find({"label": True})
                .sort("timestamp", DESCENDING)
                .limit(n)
            )

            if not docs:
                return []

            docs.reverse()  # evaluar en orden cronológico ascendente
            return [self._doc_to_input(d) for d in docs]

        except PyMongoError as e:
            logger.error(f"Error fetching bootstrap messages: {e}")
            return []

    def count_bootstrap_candidates(self) -> int:
        """Cuenta cuántos documentos relevantes existen para poder iniciar bootstrap."""
        try:
            return self.message_backup.count_documents({"label": True})
        except PyMongoError as e:
            logger.error(f"Error contando candidatos bootstrap: {e}")
            return 0

    def _pending_ragas_query(self) -> dict:
        """
        Query central de pendientes RAGAS.

        Regla:
        - label=True: mensaje relevante/candidato.
        - timestamp > ragas_bootstrap_at: ignora histórico anterior al bootstrap.
        - ragas_evaluated != True: aún no fue evaluado por RAGAS.
        """
        if not self.state.ragas_initialized or not self.state.ragas_bootstrap_at:
            return {
                "_id": {"$exists": False}
            }

        return {
            "label": True,
            "timestamp": {"$gt": self.state.ragas_bootstrap_at},
            "ragas_evaluated": {"$ne": True},
        }

    def count_pending_ragas_messages(self) -> int:
        """Cuenta mensajes relevantes pendientes después del bootstrap."""
        try:
            return self.message_backup.count_documents(self._pending_ragas_query())
        except PyMongoError as e:
            logger.error(f"Error contando pendientes RAGAS: {e}")
            return 0

    def fetch_pending_ragas_messages(self, limit: int = WINDOW_SIZE) -> list[EvaluationInput]:
        """
        Trae mensajes pendientes RAGAS en orden cronológico.

        Importante:
        No depende solo de last_evaluated_at.
        Usa ragas_bootstrap_at + ragas_evaluated != True.
        """
        try:
            docs = list(
                self.message_backup
                .find(self._pending_ragas_query())
                .sort("timestamp", ASCENDING)
                .limit(limit)
            )

            if not docs:
                return []

            return [self._doc_to_input(d) for d in docs]

        except PyMongoError as e:
            logger.error(f"Error fetching pending RAGAS messages: {e}")
            return []

    def _mark_messages_as_ragas_evaluated(
        self,
        results: list[EvaluationResult],
        window_id: str,
        batch_type: str,
    ):
        """
        Marca los documentos originales en message_backup como evaluados por RAGAS.

        Si falla, lanza excepción para NO avanzar estado.
        """
        if not results:
            raise RuntimeError("No hay resultados para marcar como evaluados.")

        evaluated_at = self._now_utc()
        operations = []

        for r in results:
            try:
                obj_id = ObjectId(r.doc_id)
            except Exception as e:
                raise RuntimeError(f"doc_id inválido para ObjectId: {r.doc_id}") from e

            operations.append(
                UpdateOne(
                    {"_id": obj_id},
                    {
                        "$set": {
                            "ragas_evaluated": True,
                            "ragas_evaluated_at": evaluated_at,
                            "ragas_window_id": window_id,
                            "ragas_batch_type": batch_type,
                            "ragas_evaluator_model": self.evaluator_model,
                            "ragas_final_score": r.final_score,
                            "ragas_scores": {
                                "faithfulness": r.faithfulness.score,
                                "answer_relevancy": r.answer_relevancy.score,
                                "context_precision": r.context_precision.score,
                                "context_recall": r.context_recall.score,
                            },
                        }
                    },
                )
            )

        try:
            bulk_result = self.message_backup.bulk_write(operations, ordered=True)

            if bulk_result.matched_count != len(results):
                raise RuntimeError(
                    f"Solo se encontraron {bulk_result.matched_count}/{len(results)} "
                    f"documentos para marcar como RAGAS evaluados."
                )

        except Exception as e:
            # Intento de rollback parcial si el bulk alcanzó a marcar algunos.
            try:
                ids = [ObjectId(r.doc_id) for r in results]
                self.message_backup.update_many(
                    {
                        "_id": {"$in": ids},
                        "ragas_window_id": window_id,
                    },
                    {
                        "$unset": {
                            "ragas_evaluated": "",
                            "ragas_evaluated_at": "",
                            "ragas_window_id": "",
                            "ragas_batch_type": "",
                            "ragas_evaluator_model": "",
                            "ragas_final_score": "",
                            "ragas_scores": "",
                        }
                    },
                )
            except Exception as rollback_error:
                logger.error(f"Rollback RAGAS falló: {rollback_error}")

            raise RuntimeError(
                f"No se pudieron marcar documentos como evaluados en MongoDB: {e}"
            ) from e

    # ================================================================== #
    # ESTADO PERSISTENTE (eval_state.json)                                 #
    # ================================================================== #

    def _load_state(self) -> EvaluationState:
        """Carga el estado desde el archivo JSON."""
        if not self.state_file.exists():
            logger.info("📄 Estado no encontrado, iniciando evaluador desde cero.")
            return EvaluationState()
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Pydantic se encarga de validar/parsear datetimes ISO
            state = EvaluationState.model_validate(data)
            logger.info(f"✅ Estado cargado desde {self.state_file}")
            return state
        except Exception as e:
            logger.error(f"❌ Error cargando estado ({e}), iniciando desde cero.")
            return EvaluationState()

    def _save_state(self):
        """Guarda el estado de forma atómica (.tmp → rename)."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_file.with_suffix(".tmp")
        try:
            data = self.state.model_dump(mode="json")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.state_file)
            logger.debug(f"💾 Estado guardado en {self.state_file}")
        except Exception as e:
            logger.error(f"❌ Error guardando estado: {e}")
            if tmp_path.exists():
                tmp_path.unlink()

    # ================================================================== #
    # FETCH                                                                #
    # ================================================================== #

    def _doc_to_input(self, doc: dict) -> EvaluationInput:
        """Convierte un doc de Mongo a EvaluationInput, recuperando contexto previo."""
        previous = list(
            self.message_backup
            .find({
                "session_id": doc.get("session_id"),
                "timestamp":  {"$lt": doc.get("timestamp")},
                "label":      True,
            })
            .sort("timestamp", DESCENDING)
            .limit(4)
        )
        previous_messages = []
        for p in reversed(previous):
            previous_messages.append({"role": "human", "content": p.get("question", "")})
            if p.get("answer"):
                previous_messages.append({"role": "assistant", "content": p.get("answer", "")})

        return EvaluationInput(
            doc_id=str(doc["_id"]),
            session_id=doc.get("session_id", "unknown"),
            question=doc.get("question", ""),
            answer=doc.get("answer", ""),
            verbose_log=doc.get("verbose_log", ""),
            timestamp=doc.get("timestamp", datetime.now(timezone.utc)),
            previous_messages=previous_messages,
        )

    def fetch_last_messages(self, n: Optional[int] = None) -> list[EvaluationInput]:
        """Modo NORMAL: trae los últimos N mensajes (orden cronológico ascendente)."""
        n = n or self.n_last
        try:
            docs = list(
                self.message_backup
                .find({"label": True})
                .sort("timestamp", DESCENDING)
                .limit(n)
            )
            if not docs:
                logger.warning("No se encontraron mensajes para evaluar.")
                return []
            docs.reverse()  # cronológico ascendente
            inputs = [self._doc_to_input(d) for d in docs]
            logger.info(f"✅ Fetched {len(inputs)} mensajes (modo normal).")
            return inputs
        except PyMongoError as e:
            logger.error(f"Error fetching messages: {e}")
            return []

    def fetch_after(self, since: datetime, limit: int = 200) -> list[EvaluationInput]:
        """Modo SLIDING: trae mensajes con timestamp > since, ascendente."""
        try:
            docs = list(
                self.message_backup
                .find({"label": True, "timestamp": {"$gt": since}})
                .sort("timestamp", ASCENDING)
                .limit(limit)
            )
            if not docs:
                return []
            return [self._doc_to_input(d) for d in docs]
        except PyMongoError as e:
            logger.error(f"Error fetching messages after {since}: {e}")
            return []

    # ================================================================== #
    # EVALUACIÓN DE 1 DOC                                                  #
    # ================================================================== #

    async def evaluate_single(self, inp: EvaluationInput) -> EvaluationResult:
        logger.info(f"📊 Evaluando doc_id={inp.doc_id} | Q: {inp.question[:60]}...")

        faithfulness, answer_relevancy, context_precision, context_recall = await asyncio.gather(
            evaluate_faithfulness(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            evaluate_answer_relevancy(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            evaluate_context_precision(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            evaluate_context_recall(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            return_exceptions=True,
        )

        def safe_metric(result, name: str) -> MetricScore:
            if isinstance(result, Exception):
                logger.error(f"Métrica {name} falló: {result}")
                return MetricScore(score=0.5, reasoning=f"Error en {name}: {result}")
            return result

        faithfulness      = safe_metric(faithfulness, "faithfulness")
        answer_relevancy  = safe_metric(answer_relevancy, "answer_relevancy")
        context_precision = safe_metric(context_precision, "context_precision")
        context_recall    = safe_metric(context_recall, "context_recall")

        final_score = (
            faithfulness.score      * METRIC_WEIGHTS["faithfulness"] +
            answer_relevancy.score  * METRIC_WEIGHTS["answer_relevancy"] +
            context_precision.score * METRIC_WEIGHTS["context_precision"] +
            context_recall.score    * METRIC_WEIGHTS["context_recall"]
        )

        return EvaluationResult(
            doc_id=inp.doc_id,
            session_id=inp.session_id,
            question=inp.question,
            answer=inp.answer,
            timestamp=inp.timestamp,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
            final_score=round(final_score, 4),
            evaluator_model=self.evaluator_model,
        )

    # ================================================================== #
    # BATCH (modo normal o sliding)                                        #
    # ================================================================== #

    async def evaluate_batch(
        self,
        mode: Literal["normal", "sliding"] = "normal",
    ) -> list[EvaluationResult]:
        if mode == "sliding":
            return await self._evaluate_sliding_window()
        return await self._evaluate_normal()

    async def _evaluate_normal(self) -> list[EvaluationResult]:
        """Evalúa los últimos N (sin afectar el estado de la ventana)."""
        inputs = self.fetch_last_messages()
        if not inputs:
            return []

        results = []
        for i, inp in enumerate(inputs):
            try:
                r = await self.evaluate_single(inp)
                results.append(r)
                self._save_to_json(r)
                self._save_to_mongo(r)
                logger.info(f"[{i+1}/{len(inputs)}] ✅ {inp.doc_id} | score={r.final_score:.3f}")
            except Exception as e:
                logger.error(f"Error evaluando {inp.doc_id}: {e}")

        self._print_summary(results)
        self._save_batch_summary(results)
        return results

    async def bootstrap_latest_window(self) -> list[EvaluationResult]:
        """
        Momento 0:
        evalúa los últimos WINDOW_SIZE documentos relevantes actuales.

        Si sale bien:
        - marca esos 10 como ragas_evaluated=True
        - inicializa ragas_bootstrap_at
        - inicializa last_evaluated_at
        - limpia historial anterior del estado local
        """
        inputs = self.fetch_latest_bootstrap_messages(n=WINDOW_SIZE)

        if len(inputs) < WINDOW_SIZE:
            msg = (
                f"No hay suficientes documentos relevantes para iniciar RAGAS. "
                f"Se encontraron {len(inputs)}, se requieren {WINDOW_SIZE}."
            )
            self._set_last_error(msg)
            logger.warning(msg)
            return []

        try:
            return await self._evaluate_ragas_window(
                inputs=inputs,
                batch_type="bootstrap",
            )

        except Exception as e:
            msg = f"Falló el bootstrap RAGAS. No se avanzó estado. Error: {e}"
            self._set_last_error(msg)
            logger.exception(msg)
            raise

    async def evaluate_ready_windows(
        self,
        max_batches: int = 5,
    ) -> list[EvaluationResult]:
        """
        Evalúa todos los batches completos disponibles, con límite.

        Ejemplo:
        - Si hay 22 pendientes y max_batches=5:
          evalúa 2 batches = 20 docs, deja 2 pendientes.

        Si un batch falla:
        - los batches anteriores exitosos quedan cerrados
        - el batch fallido no avanza cursor
        - se lanza error para mostrar en UI
        """
        all_results: list[EvaluationResult] = []
        batches_done = 0

        while batches_done < max_batches:
            pending = self.count_pending_ragas_messages()

            if pending < WINDOW_SIZE:
                break

            try:
                results = await self._evaluate_sliding_window()

                if not results:
                    break

                all_results.extend(results)
                batches_done += 1

            except Exception as e:
                msg = (
                    f"Falló la evaluación masiva después de "
                    f"{batches_done} batch(es) completado(s). "
                    f"El batch actual no se cerró. Error: {e}"
                )
                self._set_last_error(msg)
                logger.exception(msg)
                raise RuntimeError(msg) from e

        return all_results

    async def _evaluate_sliding_window(self) -> list[EvaluationResult]:
        """
        Evalúa UNA ventana de WINDOW_SIZE mensajes relevantes pendientes.

        Requiere que primero exista bootstrap.
        """
        if not self.state.ragas_initialized or not self.state.ragas_bootstrap_at:
            msg = (
                "RAGAS aún no está inicializado. "
                "Primero ejecuta bootstrap_latest_window()."
            )
            logger.warning(msg)
            return []

        inputs = self.fetch_pending_ragas_messages(limit=WINDOW_SIZE)

        if len(inputs) < WINDOW_SIZE:
            logger.info(
                f"⏭️ Solo hay {len(inputs)} mensajes relevantes nuevos "
                f"(< {WINDOW_SIZE}), no se evalúa."
            )
            return []

        try:
            return await self._evaluate_ragas_window(
                inputs=inputs,
                batch_type="sliding",
            )

        except Exception as e:
            msg = f"Falló la evaluación del siguiente batch. No se avanzó estado. Error: {e}"
            self._set_last_error(msg)
            logger.exception(msg)
            raise

    async def _evaluate_ragas_window(
        self,
        inputs: list[EvaluationInput],
        batch_type: Literal["bootstrap", "sliding"],
    ) -> list[EvaluationResult]:
        """
        Evalúa una ventana completa de RAGAS de forma transaccional a nivel lógico.

        Regla:
        - Si no hay exactamente WINDOW_SIZE inputs, no evalúa.
        - Primero evalúa todos.
        - Si todos salen bien, marca Mongo.
        - Luego guarda JSONs y actualiza estado.
        - Si algo falla antes de actualizar estado, el batch se puede reintentar completo.
        """
        if len(inputs) < WINDOW_SIZE:
            logger.info(
                f"⏭️ Ventana incompleta: {len(inputs)}/{WINDOW_SIZE}. No se evalúa."
            )
            return []

        window_inputs = inputs[:WINDOW_SIZE]
        window_id = self._build_window_id(batch_type)

        logger.info(
            f"📊 Evaluando ventana RAGAS tipo={batch_type} "
            f"window_id={window_id} docs={len(window_inputs)}"
        )

        results: list[EvaluationResult] = []

        # 1) Evaluar todos los documentos primero.
        for i, inp in enumerate(window_inputs):
            try:
                r = await self.evaluate_single(inp)
                results.append(r)
                logger.info(
                    f"[{i + 1}/{len(window_inputs)}] ✅ {inp.doc_id} "
                    f"| score={r.final_score:.3f}"
                )

            except Exception as e:
                msg = (
                    f"Error evaluando doc_id={inp.doc_id}. "
                    f"No se cerrará la ventana {window_id}. Error: {e}"
                )
                logger.exception(msg)
                raise RuntimeError(msg) from e

        if len(results) != WINDOW_SIZE:
            raise RuntimeError(
                f"La ventana produjo {len(results)}/{WINDOW_SIZE} resultados. "
                f"No se cerrará el batch."
            )

        # 2) Calcular promedios.
        n = len(results)
        averages = {
            "faithfulness":      round(sum(r.faithfulness.score      for r in results) / n, 4),
            "answer_relevancy":  round(sum(r.answer_relevancy.score  for r in results) / n, 4),
            "context_precision": round(sum(r.context_precision.score for r in results) / n, 4),
            "context_recall":    round(sum(r.context_recall.score    for r in results) / n, 4),
            "final_score":       round(sum(r.final_score             for r in results) / n, 4),
        }

        # 3) Marcar Mongo antes de avanzar estado.
        # Si esto falla, lanzará excepción y NO se actualizará eval_state.json.
        self._mark_messages_as_ragas_evaluated(
            results=results,
            window_id=window_id,
            batch_type=batch_type,
        )

        # 4) Guardar resultados individuales.
        for r in results:
            self._save_to_json(r)
            self._save_to_mongo(r)

        # 5) Si es bootstrap, reseteamos estado anterior local.
        # Esto evita que evaluaciones viejas de prueba aparezcan en la UI.
        if batch_type == "bootstrap":
            self.state = EvaluationState()
            self.state.ragas_initialized = True

            latest_ts = max(r.timestamp for r in results)
            latest_doc_id = results[-1].doc_id

            self.state.ragas_bootstrap_at = latest_ts
            self.state.ragas_bootstrap_doc_id = latest_doc_id

        # 6) Actualizar cursor y estado.
        latest_ts = max(r.timestamp for r in results)

        self.state.last_evaluated_doc_id = results[-1].doc_id
        self.state.last_evaluated_at = latest_ts
        self.state.last_score = averages["final_score"]
        self.state.last_averages = averages

        self.state.history.append(WindowEntry(
            evaluated_at=self._now_utc(),
            window_start_doc_id=results[0].doc_id,
            window_end_doc_id=results[-1].doc_id,
            n_evaluated=n,
            averages=averages,
            final_score=averages["final_score"],
        ))

        self._clear_last_error()
        self._save_state()
        self._save_batch_summary(results)
        self._print_summary(results)

        logger.info(
            f"✅ Ventana RAGAS completada: "
            f"type={batch_type} | window_id={window_id} | "
            f"{n} docs | final_score={averages['final_score']:.4f}"
        )

        return results

    # ================================================================== #
    # PERSISTENCIA — JSON                                                  #
    # ================================================================== #

    def _result_to_dict(self, result: EvaluationResult) -> dict:
        return {
            "doc_id":          result.doc_id,
            "session_id":      result.session_id,
            "question":        result.question,
            "answer":          result.answer,
            "timestamp":       result.timestamp.isoformat(),
            "evaluated_at":    result.evaluated_at.isoformat(),
            "evaluator_model": result.evaluator_model,
            "scores": {
                "faithfulness":      {"score": result.faithfulness.score,      "reasoning": result.faithfulness.reasoning,      "details": result.faithfulness.details},
                "answer_relevancy":  {"score": result.answer_relevancy.score,  "reasoning": result.answer_relevancy.reasoning,  "details": result.answer_relevancy.details},
                "context_precision": {"score": result.context_precision.score, "reasoning": result.context_precision.reasoning, "details": result.context_precision.details},
                "context_recall":    {"score": result.context_recall.score,    "reasoning": result.context_recall.reasoning,    "details": result.context_recall.details},
            },
            "final_score":  result.final_score,
            "weights_used": METRIC_WEIGHTS,
        }

    def _save_to_json(self, result: EvaluationResult):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            filepath = self.output_dir / f"eval_{result.doc_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._result_to_dict(result), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando JSON de {result.doc_id}: {e}")

    def _save_batch_summary(self, results: list[EvaluationResult]):
        if not results:
            return
        try:
            n = len(results)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filepath = self.output_dir / f"summary_{timestamp_str}.json"
            summary = {
                "evaluated_at":    datetime.now(timezone.utc).isoformat(),
                "evaluator_model": self.evaluator_model,
                "n_evaluated":     n,
                "weights_used":    METRIC_WEIGHTS,
                "averages": {
                    "faithfulness":      round(sum(r.faithfulness.score      for r in results) / n, 4),
                    "answer_relevancy":  round(sum(r.answer_relevancy.score  for r in results) / n, 4),
                    "context_precision": round(sum(r.context_precision.score for r in results) / n, 4),
                    "context_recall":    round(sum(r.context_recall.score    for r in results) / n, 4),
                    "final_score":       round(sum(r.final_score              for r in results) / n, 4),
                },
                "results": [self._result_to_dict(r) for r in results],
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            logger.info(f"📁 Resumen guardado en: {filepath}")
        except Exception as e:
            logger.error(f"Error guardando batch summary: {e}")

    # ================================================================== #
    # PERSISTENCIA — MongoDB (opcional)                                    #
    # ================================================================== #

    def _save_to_mongo(self, result: EvaluationResult):
        if not self._mongo_write_available or self.eval_collection is None:
            return
        try:
            doc = self._result_to_dict(result)
            doc["timestamp"]    = result.timestamp
            doc["evaluated_at"] = result.evaluated_at
            self.eval_collection.update_one(
                {"doc_id": result.doc_id}, {"$set": doc}, upsert=True
            )
        except PyMongoError as e:
            logger.warning(f"⚠️ No se pudo guardar en Mongo (doc {result.doc_id}): {e}")

    # ================================================================== #
    # RESUMEN                                                              #
    # ================================================================== #

    def _print_summary(self, results: list[EvaluationResult]):
        if not results:
            return
        n = len(results)
        avg_f = sum(r.faithfulness.score      for r in results) / n
        avg_r = sum(r.answer_relevancy.score  for r in results) / n
        avg_p = sum(r.context_precision.score for r in results) / n
        avg_c = sum(r.context_recall.score    for r in results) / n
        avg_t = sum(r.final_score              for r in results) / n
        summary = f"""
╔══════════════════════════════════════════════════╗
║         RAGAS EVALUATION SUMMARY                 ║
╠══════════════════════════════════════════════════╣
║  Documentos evaluados : {n:<25}║
║  Faithfulness         : {avg_f:.3f} (peso: {METRIC_WEIGHTS['faithfulness']:.0%})         ║
║  Answer Relevancy     : {avg_r:.3f} (peso: {METRIC_WEIGHTS['answer_relevancy']:.0%})         ║
║  Context Precision    : {avg_p:.3f} (peso: {METRIC_WEIGHTS['context_precision']:.0%})         ║
║  Context Recall       : {avg_c:.3f} (peso: {METRIC_WEIGHTS['context_recall']:.0%})         ║
╠══════════════════════════════════════════════════╣
║  ⭐ SCORE FINAL       : {avg_t:.3f}                     ║
╚══════════════════════════════════════════════════╝
"""
        print(summary)
        logger.info(summary)

    def get_latest_summary(self) -> Optional[dict]:
        """Resumen más reciente: primero del state, fallback a summary_*.json."""
        if self.state.last_averages:
            return {
                "evaluated_at":    self.state.last_evaluated_at.isoformat() if self.state.last_evaluated_at else None,
                "evaluator_model": self.evaluator_model,
                "n_evaluated":     self.state.history[-1].n_evaluated if self.state.history else 0,
                "weights_used":    METRIC_WEIGHTS,
                "averages":        self.state.last_averages,
            }
        try:
            files = sorted(self.output_dir.glob("summary_*.json"), reverse=True)
            if files:
                with open(files[0], "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error leyendo summary: {e}")
        return None