from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ct.evaluation.schemas import FaithfulnessResponse, MetricScore
from ct.evaluation.prompts import FAITHFULNESS_PROMPT
import logging
import re

logger = logging.getLogger(__name__)


def parse_tool_outputs(verbose_log: str) -> str:
    """Extrae solo los outputs de las tools del verbose_log."""
    if not verbose_log:
        return "No se usaron herramientas."
    
    lines = verbose_log.split("\n")
    tool_outputs = [
        line for line in lines 
        if line.startswith("🛠️ [Tool Output")
    ]
    
    if not tool_outputs:
        return "No se usaron herramientas."
    
    return "\n".join(tool_outputs)


async def evaluate_faithfulness(
    question: str,
    answer: str,
    verbose_log: str,
    llm: ChatOpenAI
) -> MetricScore:
    
    tool_outputs = parse_tool_outputs(verbose_log)
    
    prompt = FAITHFULNESS_PROMPT.format(
        question=question,
        tool_outputs=tool_outputs,
        answer=answer
    )
    
    structured_llm = llm.with_structured_output(FaithfulnessResponse)
    
    try:
        response_raw = await structured_llm.ainvoke([
    HumanMessage(content=prompt)
        ])

        if isinstance(response_raw, FaithfulnessResponse):
            response = response_raw
        else:
            response = FaithfulnessResponse.model_validate(response_raw)
        
        return MetricScore(
            score=response.score,
            reasoning=response.reasoning,
            details={
                "claims_supported": response.claims_supported,
                "claims_total": response.claims_total
            }
        )
    except Exception as e:
        logger.error(f"Error evaluando faithfulness: {e}")
        return MetricScore(
            score=0.5,
            reasoning=f"Error en evaluación: {str(e)}",
            details={}
        )