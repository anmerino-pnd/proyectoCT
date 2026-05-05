from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class ToolCall(BaseModel):
    tool_name: str
    args: dict
    output: str


class EvaluationInput(BaseModel):
    doc_id: str
    session_id: str
    question: str
    answer: str
    verbose_log: str
    timestamp: datetime
    previous_messages: list[dict] = Field(
        default_factory=list,
        description="Últimos mensajes de la conversación para dar contexto"
    )


class MetricScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    details: Optional[dict] = None


class EvaluationResult(BaseModel):
    doc_id: str
    session_id: str
    question: str
    answer: str
    timestamp: datetime

    faithfulness: MetricScore
    answer_relevancy: MetricScore
    context_precision: MetricScore
    context_recall: MetricScore

    final_score: float
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now())
    evaluator_model: str


class FaithfulnessResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Score entre 0 y 1")
    reasoning: str = Field(description="Explicación del score")
    claims_supported: int = Field(description="Número de afirmaciones soportadas")
    claims_total: int = Field(description="Número total de afirmaciones")


class AnswerRelevancyResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    is_complete: bool = Field(description="¿La respuesta responde completamente?")
    has_noise: bool = Field(description="¿Hay información irrelevante que confunde?")
    noise_severity: str = Field(default="NINGUNO", description="NINGUNO | MENOR | GRAVE")


class ContextPrecisionResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    tools_used: list[str]
    tools_relevant: list[str]
    tools_irrelevant: list[str]


class ContextRecallResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    missing_tools: list[str] = Field(description="Tools que deberían haberse usado")
    coverage: str = Field(description="Descripción de qué tan bien se cubrió la pregunta")


class WindowEntry(BaseModel):
    """Registro de una evaluación de ventana completada."""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    window_start_doc_id: str
    window_end_doc_id: str
    n_evaluated: int = Field(default=10, description="Número de documentos evaluados en este ventana")
    averages: dict = Field(
        description="Promedios de métricas del ventana"
    )
    final_score: float = Field(description="Score final del ventana")


class EvaluationState(BaseModel):
    """Estado del evaluador RAG con ventana deslizante."""

    # Cursor principal
    last_evaluated_doc_id: Optional[str] = None
    last_evaluated_at: Optional[datetime] = None

    # Estado de bootstrap RAGAS
    ragas_initialized: bool = False
    ragas_bootstrap_at: Optional[datetime] = None
    ragas_bootstrap_doc_id: Optional[str] = None

    # Últimas métricas
    last_score: Optional[float] = None
    last_averages: Optional[dict] = None

    # Errores visibles en UI
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None

    # Historial de ventanas
    history: list[WindowEntry] = Field(
        default_factory=list,
        description="Historial de ventanas evaluadas"
    )