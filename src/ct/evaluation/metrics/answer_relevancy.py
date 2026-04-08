from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ct.evaluation.schemas import AnswerRelevancyResponse, MetricScore
from ct.evaluation.prompts import ANSWER_RELEVANCY_PROMPT
import logging
import re

logger = logging.getLogger(__name__)


def extract_tool_names(verbose_log: str) -> str:
    """Extrae nombres de tools usadas."""
    if not verbose_log:
        return "Ninguna"
    
    lines = verbose_log.split("\n")
    tool_names = []
    
    for line in lines:
        if "decidió usar:" in line:
            tool_name = line.split("decidió usar:")[-1].strip()
            tool_names.append(tool_name)
    
    return ", ".join(tool_names) if tool_names else "Ninguna"


async def evaluate_answer_relevancy(
    question: str,
    answer: str,
    verbose_log: str,
    llm: ChatOpenAI
) -> MetricScore:
    
    tool_names = extract_tool_names(verbose_log)
    
    prompt = ANSWER_RELEVANCY_PROMPT.format(
        question=question,
        answer=answer,
        tool_names=tool_names
    )
    
    structured_llm = llm.with_structured_output(AnswerRelevancyResponse)
    
    try:
        response_raw = await structured_llm.ainvoke([
    HumanMessage(content=prompt)
        ])

        if isinstance(response_raw, AnswerRelevancyResponse):
            response = response_raw
        else:
            response = AnswerRelevancyResponse.model_validate(response_raw)
        
        return MetricScore(
            score=response.score,
            reasoning=response.reasoning,
            details={
                "is_complete": response.is_complete,
                "has_hallucinations": response.has_hallucinations
            }
        )
    except Exception as e:
        logger.error(f"Error evaluando answer relevancy: {e}")
        return MetricScore(
            score=0.5,
            reasoning=f"Error en evaluación: {str(e)}",
            details={}
        )