import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import SecretStr
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError
from langchain_openai import ChatOpenAI

from ct.evaluation.schemas import EvaluationInput, EvaluationResult, MetricScore
from ct.evaluation.metrics.faithfulness import evaluate_faithfulness
from ct.evaluation.metrics.answer_relevancy import evaluate_answer_relevancy
from ct.evaluation.metrics.context_precision import evaluate_context_precision
from ct.evaluation.metrics.context_recall import evaluate_context_recall
from ct.settings.clients import mongo_uri, mongo_collection_message_backup, openai_api_key

logger = logging.getLogger(__name__)


# Pesos de cada métrica en el score final
METRIC_WEIGHTS = {
    "faithfulness": 0.30,
    "answer_relevancy": 0.35,
    "context_precision": 0.15,
    "context_recall": 0.20,
}


class RAGASEvaluator:
    """
    Evaluador de respuestas del ToolAgent usando métricas inspiradas en RAGAS.
    Evalúa las últimas N respuestas almacenadas en MongoDB.
    """

    def __init__(
        self, 
        evaluator_model: str = "gpt-4o-mini",
        n_last: int = 10,
        eval_collection: str = "evaluation_results"
    ):
        self.evaluator_model = evaluator_model
        self.n_last = n_last
        self.eval_collection_name = eval_collection

        # LLM evaluador — separado del LLM del agente
        self.llm = ChatOpenAI(
            model=self.evaluator_model,
            temperature=0,  # Determinístico para evaluaciones
            api_key=SecretStr(openai_api_key)
        )

        # MongoDB
        self.client = MongoClient(mongo_uri).get_default_database()
        self.message_backup = self.client[mongo_collection_message_backup]
        self.eval_collection = self.client[eval_collection]

    # ------------------------------------------------------------------ #
    # Fetch de datos                                                        #
    # ------------------------------------------------------------------ #

    def fetch_last_messages(self) -> list[EvaluationInput]:
        """Obtiene los últimos N mensajes de MongoDB."""
        try:
            docs = list(
                self.message_backup
                .find({"label": True})   # Solo mensajes válidos
                .sort("timestamp", DESCENDING)
                .limit(self.n_last)
            )
            
            if not docs:
                logger.warning("No se encontraron mensajes para evaluar.")
                return []

            inputs = []
            for doc in docs:
                inputs.append(EvaluationInput(
                    doc_id=str(doc["_id"]),
                    session_id=doc.get("session_id", "unknown"),
                    question=doc.get("question", ""),
                    answer=doc.get("answer", ""),
                    verbose_log=doc.get("verbose_log", ""),
                    timestamp=doc.get("timestamp", datetime.now(timezone.utc))
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

        # Ejecutar las 4 métricas en paralelo para eficiencia
        faithfulness, answer_relevancy, context_precision, context_recall = await asyncio.gather(
            evaluate_faithfulness(inp.question, inp.answer, inp.verbose_log, self.llm),
            evaluate_answer_relevancy(inp.question, inp.answer, inp.verbose_log, self.llm),
            evaluate_context_precision(inp.question, inp.answer, inp.verbose_log, self.llm),
            evaluate_context_recall(inp.question, inp.answer, inp.verbose_log, self.llm),
            return_exceptions=True  # No fallar si una métrica falla
        )

        # Fallback si alguna métrica devolvió excepción
        def safe_metric(result, name: str) -> MetricScore:
            if isinstance(result, Exception):
                logger.error(f"Métrica {name} falló: {result}")
                return MetricScore(score=0.5, reasoning=f"Error: {str(result)}")
            return result

        faithfulness = safe_metric(faithfulness, "faithfulness")
        answer_relevancy = safe_metric(answer_relevancy, "answer_relevancy")
        context_precision = safe_metric(context_precision, "context_precision")
        context_recall = safe_metric(context_recall, "context_recall")

        # Score final ponderado
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
        
        # Evaluar secuencialmente para evitar rate limits
        for i, inp in enumerate(inputs):
            try:
                result = await self.evaluate_single(inp)
                results.append(result)
                self._save_result(result)
                logger.info(
                    f"[{i+1}/{len(inputs)}] ✅ doc_id={inp.doc_id} "
                    f"| Final Score: {result.final_score:.3f}"
                )
                
                # Pequeña pausa para respetar rate limits del LLM evaluador
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error evaluando doc {inp.doc_id}: {e}")
                continue

        # Resumen final
        self._print_summary(results)
        return results

    # ------------------------------------------------------------------ #
    # Persistencia                                                         #
    # ------------------------------------------------------------------ #

    def _save_result(self, result: EvaluationResult):
        """Guarda el resultado de evaluación en MongoDB."""
        try:
            doc = {
                "doc_id": result.doc_id,
                "session_id": result.session_id,
                "question": result.question,
                "answer": result.answer,
                "timestamp": result.timestamp,
                "evaluated_at": result.evaluated_at,
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
            
            # Upsert por doc_id para evitar duplicados
            self.eval_collection.update_one(
                {"doc_id": result.doc_id},
                {"$set": doc},
                upsert=True
            )
            
        except PyMongoError as e:
            logger.error(f"Error guardando resultado: {e}")

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
        """Obtiene el resumen de la última evaluación batch desde MongoDB."""
        try:
            results = list(
                self.eval_collection
                .find({})
                .sort("evaluated_at", DESCENDING)
                .limit(self.n_last)
            )
            
            if not results:
                return None
            
            n = len(results)
            return {
                "n_evaluated": n,
                "avg_faithfulness": sum(r["scores"]["faithfulness"]["score"] for r in results) / n,
                "avg_answer_relevancy": sum(r["scores"]["answer_relevancy"]["score"] for r in results) / n,
                "avg_context_precision": sum(r["scores"]["context_precision"]["score"] for r in results) / n,
                "avg_context_recall": sum(r["scores"]["context_recall"]["score"] for r in results) / n,
                "avg_final_score": sum(r["final_score"] for r in results) / n,
                "last_evaluated_at": results[0]["evaluated_at"]
            }
        except Exception as e:
            logger.error(f"Error getting summary: {e}")
            return None