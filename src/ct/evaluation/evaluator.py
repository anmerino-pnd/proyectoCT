import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from pydantic import SecretStr
from pymongo.errors import PyMongoError
from langchain_openai import ChatOpenAI
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

from ct.settings.config import EVAL_OUTPUT_DIR
from ct.evaluation.metrics.faithfulness import evaluate_faithfulness
from ct.evaluation.metrics.context_recall import evaluate_context_recall
from ct.evaluation.metrics.answer_relevancy import evaluate_answer_relevancy
from ct.evaluation.metrics.context_precision import evaluate_context_precision
from ct.evaluation.schemas import EvaluationInput, EvaluationResult, MetricScore
from ct.settings.clients import mongo_uri, mongo_collection_message_backup, openai_api_key

logger = logging.getLogger(__name__)

METRIC_WEIGHTS = {
    "faithfulness": 0.40,       # Lo más crítico — precios mal = problema real
    "answer_relevancy": 0.35,   # Segundo — que responda lo que le preguntaron
    "context_precision": 0.125, # Equilibrio entre sí mismas
    "context_recall": 0.125,    # Equilibrio entre sí mismas
}

class RAGASEvaluator:
    def __init__(
        self,
        evaluator_model: str = "gpt-4o-mini",
        n_last: int = 10,
        eval_collection: str = "evaluation_results",
        output_dir: Path = EVAL_OUTPUT_DIR
    ):
        self.evaluator_model = evaluator_model
        self.n_last = n_last
        self.output_dir = output_dir

        self.llm = ChatOpenAI(
            model=self.evaluator_model,
            temperature=0,
            api_key=SecretStr(openai_api_key)
        )

        # MongoDB — solo lectura garantizada, escritura opcional
        self.client = MongoClient(mongo_uri).get_default_database()
        self.message_backup = self.client[mongo_collection_message_backup]
        
        # Intentar conectar a eval_collection pero no fallar si no hay permisos
        self._mongo_write_available = False
        try:
            self.eval_collection = self.client[eval_collection]
            # Probe rápido: intentar una operación de lectura
            self.eval_collection.find_one({})
            self._mongo_write_available = True
            logger.info("✅ MongoDB eval collection disponible para escritura.")
        except PyMongoError as e:
            logger.warning(
                f"⚠️ Sin permisos en MongoDB eval collection: {e}\n"
                f"   → Los resultados se guardarán solo en JSON ({self.output_dir})"
            )
            self.eval_collection = None

    # ------------------------------------------------------------------ #
    # Fetch de datos                                                        #
    # ------------------------------------------------------------------ #

    def fetch_last_messages(self) -> list[EvaluationInput]:
        try:
            docs = list(
                self.message_backup
                .find({"label": True})
                .sort("timestamp", DESCENDING)
                .limit(self.n_last)
            )

            if not docs:
                logger.warning("No se encontraron mensajes para evaluar.")
                return []

            inputs = []
            for doc in docs:
                # Buscar los 4 intercambios anteriores de la misma sesión
                previous = list(
                    self.message_backup
                    .find({
                        "session_id": doc.get("session_id"),
                        "timestamp": {"$lt": doc.get("timestamp")},
                        "label": True
                    })
                    .sort("timestamp", DESCENDING)
                    .limit(4)  # Los 4 intercambios anteriores
                )

                # Formatear como lista de pares Usuario/Asistente para el evaluador
                previous_messages = []
                for p in reversed(previous):
                    previous_messages.append({"role": "human", "content": p.get("question", "")})
                    if p.get("answer"):
                        previous_messages.append({"role": "assistant", "content": p.get("answer", "")})

                inputs.append(EvaluationInput(
                    doc_id=str(doc["_id"]),
                    session_id=doc.get("session_id", "unknown"),
                    question=doc.get("question", ""),
                    answer=doc.get("answer", ""),
                    verbose_log=doc.get("verbose_log", ""),
                    timestamp=doc.get("timestamp", datetime.now(timezone.utc)),
                    previous_messages=previous_messages
                ))

            logger.info(f"✅ Fetched {len(inputs)} mensajes para evaluar.")
            return inputs

        except PyMongoError as e:
            logger.error(f"Error fetching messages: {e}")
            return []

    # ------------------------------------------------------------------ #
    # Evaluación de un único documento                                     #
    # ------------------------------------------------------------------ #

    async def evaluate_single(self, inp: EvaluationInput) -> EvaluationResult:
        """Evalúa un único par pregunta-respuesta con las 4 métricas en paralelo."""

        logger.info(f"📊 Evaluando doc_id={inp.doc_id} | Q: {inp.question[:60]}...")

        faithfulness, answer_relevancy, context_precision, context_recall = await asyncio.gather(
            evaluate_faithfulness(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            evaluate_answer_relevancy(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            evaluate_context_precision(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            evaluate_context_recall(inp.question, inp.answer, inp.verbose_log, self.llm, inp.previous_messages),
            return_exceptions=True
        )

        def safe_metric(result, name: str) -> MetricScore:
            if isinstance(result, Exception):
                logger.error(f"Métrica {name} falló con error: {result}")
                return MetricScore(score=0.5, reasoning=f"Error crítico en evaluación de {name}: {str(result)}")
            return result

        faithfulness = safe_metric(faithfulness, "faithfulness")
        answer_relevancy = safe_metric(answer_relevancy, "answer_relevancy")
        context_precision = safe_metric(context_precision, "context_precision")
        context_recall = safe_metric(context_recall, "context_recall")

        final_score = (
            faithfulness.score * METRIC_WEIGHTS["faithfulness"] +
            answer_relevancy.score * METRIC_WEIGHTS["answer_relevancy"] +
            context_precision.score * METRIC_WEIGHTS["context_precision"] +
            context_recall.score * METRIC_WEIGHTS["context_recall"]
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
            evaluator_model=self.evaluator_model
        )

    # ------------------------------------------------------------------ #
    # Evaluación batch                                                     #
    # ------------------------------------------------------------------ #

    async def evaluate_batch(self) -> list[EvaluationResult]:
        """Evalúa los últimos N mensajes y guarda resultados."""

        inputs = self.fetch_last_messages()

        if not inputs:
            logger.warning("No hay mensajes para evaluar.")
            return []

        results = []

        for i, inp in enumerate(inputs):
            try:
                result = await self.evaluate_single(inp)
                results.append(result)

                # 1️⃣ JSON: siempre (garantizado)
                self._save_to_json(result)

                # 2️⃣ MongoDB: solo si hay permisos
                self._save_to_mongo(result)

                logger.info(
                    f"[{i+1}/{len(inputs)}] ✅ doc_id={inp.doc_id} "
                    f"| Final Score: {result.final_score:.3f}"
                )
                # Removido sleep artificial para mejorar rendimiento,
                # ya que evaluate_single ya maneja el paralelismo interno de métricas.


            except Exception as e:
                logger.error(f"Error evaluando doc {inp.doc_id}: {e}")
                continue

        self._print_summary(results)
        
        # Guardar también el resumen batch completo en un JSON aparte
        self._save_batch_summary(results)

        return results

    # ------------------------------------------------------------------ #
    # Persistencia — JSON (siempre)                                        #
    # ------------------------------------------------------------------ #

    def _result_to_dict(self, result: EvaluationResult) -> dict:
        """Serializa un EvaluationResult a dict JSON-compatible."""
        return {
            "doc_id": result.doc_id,
            "session_id": result.session_id,
            "question": result.question,
            "answer": result.answer,
            "timestamp": result.timestamp.isoformat(),
            "evaluated_at": result.evaluated_at.isoformat(),
            "evaluator_model": result.evaluator_model,
            "scores": {
                "faithfulness": {
                    "score": result.faithfulness.score,
                    "reasoning": result.faithfulness.reasoning,
                    "details": result.faithfulness.details
                },
                "answer_relevancy": {
                    "score": result.answer_relevancy.score,
                    "reasoning": result.answer_relevancy.reasoning,
                    "details": result.answer_relevancy.details
                },
                "context_precision": {
                    "score": result.context_precision.score,
                    "reasoning": result.context_precision.reasoning,
                    "details": result.context_precision.details
                },
                "context_recall": {
                    "score": result.context_recall.score,
                    "reasoning": result.context_recall.reasoning,
                    "details": result.context_recall.details
                }
            },
            "final_score": result.final_score,
            "weights_used": METRIC_WEIGHTS
        }

    def _save_to_json(self, result: EvaluationResult):
        """
        Guarda un resultado individual como JSON.
        Archivo: evaluation_results/eval_<doc_id>.json
        """
        try:
            filepath = self.output_dir / f"eval_{result.doc_id}.json"
            doc = self._result_to_dict(result)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)

            logger.debug(f"💾 JSON guardado: {filepath}")

        except Exception as e:
            logger.error(f"Error guardando JSON para doc {result.doc_id}: {e}")

    def _save_batch_summary(self, results: list[EvaluationResult]):
        """
        Guarda un resumen del batch completo.
        Archivo: evaluation_results/summary_<timestamp>.json
        """
        if not results:
            return

        try:
            n = len(results)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filepath = self.output_dir / f"summary_{timestamp_str}.json"

            summary = {
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "evaluator_model": self.evaluator_model,
                "n_evaluated": n,
                "weights_used": METRIC_WEIGHTS,
                "averages": {
                    "faithfulness": round(sum(r.faithfulness.score for r in results) / n, 4),
                    "answer_relevancy": round(sum(r.answer_relevancy.score for r in results) / n, 4),
                    "context_precision": round(sum(r.context_precision.score for r in results) / n, 4),
                    "context_recall": round(sum(r.context_recall.score for r in results) / n, 4),
                    "final_score": round(sum(r.final_score for r in results) / n, 4),
                },
                # Todos los resultados del batch embebidos
                "results": [self._result_to_dict(r) for r in results]
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            logger.info(f"📁 Resumen del batch guardado en: {filepath}")

        except Exception as e:
            logger.error(f"Error guardando batch summary JSON: {e}")

    # ------------------------------------------------------------------ #
    # Persistencia — MongoDB (opcional)                                    #
    # ------------------------------------------------------------------ #

    def _save_to_mongo(self, result: EvaluationResult):
        """
        Intenta guardar en MongoDB.
        Si no hay permisos, loguea un warning y sigue sin romper el flujo.
        """
        if not self._mongo_write_available or self.eval_collection is None:
            return  # Silencioso — ya se avisó en __init__

        try:
            doc = self._result_to_dict(result)
            # Re-convertir timestamps a datetime para Mongo
            doc["timestamp"] = result.timestamp
            doc["evaluated_at"] = result.evaluated_at

            self.eval_collection.update_one(
                {"doc_id": result.doc_id},
                {"$set": doc},
                upsert=True
            )
            logger.debug(f"🍃 MongoDB guardado: doc_id={result.doc_id}")

        except PyMongoError as e:
            # No propagar — el JSON ya tiene los datos seguros
            logger.warning(f"⚠️ No se pudo guardar en MongoDB (doc {result.doc_id}): {e}")

    # ------------------------------------------------------------------ #
    # Resumen                                                              #
    # ------------------------------------------------------------------ #

    def _print_summary(self, results: list[EvaluationResult]):
        if not results:
            return

        n = len(results)
        avg_faithfulness = sum(r.faithfulness.score for r in results) / n
        avg_relevancy = sum(r.answer_relevancy.score for r in results) / n
        avg_precision = sum(r.context_precision.score for r in results) / n
        avg_recall = sum(r.context_recall.score for r in results) / n
        avg_final = sum(r.final_score for r in results) / n

        summary = f"""
╔══════════════════════════════════════════════════╗
║         RAGAS EVALUATION SUMMARY                 ║
╠══════════════════════════════════════════════════╣
║  Documentos evaluados : {n:<25}║
║  Faithfulness         : {avg_faithfulness:.3f} (peso: {METRIC_WEIGHTS['faithfulness']:.0%})         ║
║  Answer Relevancy     : {avg_relevancy:.3f} (peso: {METRIC_WEIGHTS['answer_relevancy']:.0%})         ║
║  Context Precision    : {avg_precision:.3f} (peso: {METRIC_WEIGHTS['context_precision']:.0%})         ║
║  Context Recall       : {avg_recall:.3f} (peso: {METRIC_WEIGHTS['context_recall']:.0%})         ║
╠══════════════════════════════════════════════════╣
║  ⭐ SCORE FINAL       : {avg_final:.3f}                     ║
╚══════════════════════════════════════════════════╝
        """
        print(summary)
        logger.info(summary)

    def get_latest_summary(self) -> Optional[dict]:
        """
        Lee el summary más reciente desde los JSONs guardados.
        Fallback total: no depende de MongoDB.
        """
        try:
            summary_files = sorted(
                self.output_dir.glob("summary_*.json"),
                reverse=True  # El más reciente primero
            )

            if not summary_files:
                logger.warning("No se encontraron summaries guardados.")
                return None

            with open(summary_files[0], "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Error leyendo summary desde JSON: {e}")
            return None