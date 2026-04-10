from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


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