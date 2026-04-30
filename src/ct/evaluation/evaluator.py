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
from pymongo import MongoClient, DESCENDING, ASCENDING

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

    async def _evaluate_sliding_window(self) -> list[EvaluationResult]:
        """
        Evalúa UNA ventana de WINDOW_SIZE mensajes nuevos.
        - Primera ejecución (state vacío): toma los últimos WINDOW_SIZE.
        - Siguientes: toma los próximos WINDOW_SIZE en orden cronológico.
        - Si no hay suficientes mensajes nuevos, no evalúa nada.
        """
        last_ts = self.state.last_evaluated_at

        if last_ts is None:
            # Primera ejecución
            logger.info("🆕 Primera ejecución: tomando los últimos 10 mensajes.")
            inputs = self.fetch_last_messages(n=WINDOW_SIZE)
        else:
            inputs = self.fetch_after(last_ts, limit=WINDOW_SIZE)

        if len(inputs) < WINDOW_SIZE:
            logger.info(
                f"⏭️ Solo hay {len(inputs)} mensajes nuevos "
                f"(< {WINDOW_SIZE}), no se evalúa."
            )
            return []

        # Tomar exactamente WINDOW_SIZE
        window_inputs = inputs[:WINDOW_SIZE]
        logger.info(f"📊 Evaluando ventana de {len(window_inputs)} documentos…")

        results: list[EvaluationResult] = []
        for inp in window_inputs:
            try:
                r = await self.evaluate_single(inp)
                results.append(r)
                self._save_to_json(r)
                self._save_to_mongo(r)
                logger.info(f"   ✅ {inp.doc_id} | score={r.final_score:.3f}")
            except Exception as e:
                logger.error(f"   ❌ Error en {inp.doc_id}: {e}")

        if not results:
            logger.warning("Ningún documento se evaluó con éxito.")
            return []

        # ---- Promedios de la ventana ----
        n = len(results)
        averages = {
            "faithfulness":      round(sum(r.faithfulness.score      for r in results) / n, 4),
            "answer_relevancy":  round(sum(r.answer_relevancy.score  for r in results) / n, 4),
            "context_precision": round(sum(r.context_precision.score for r in results) / n, 4),
            "context_recall":    round(sum(r.context_recall.score    for r in results) / n, 4),
            "final_score":       round(sum(r.final_score              for r in results) / n, 4),
        }

        # ---- Actualizar estado ----
        latest_ts = max(r.timestamp for r in results)
        self.state.last_evaluated_doc_id = results[-1].doc_id
        self.state.last_evaluated_at     = latest_ts
        self.state.last_score            = averages["final_score"]
        self.state.last_averages         = averages

        self.state.history.append(WindowEntry(
            evaluated_at=datetime.now(timezone.utc),
            window_start_doc_id=results[0].doc_id,
            window_end_doc_id=results[-1].doc_id,
            n_evaluated=n,
            averages=averages,
            final_score=averages["final_score"],
        ))

        self._save_state()
        self._save_batch_summary(results)
        self._print_summary(results)

        logger.info(
            f"✅ Ventana completada: {n} docs | final_score={averages['final_score']:.4f}"
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