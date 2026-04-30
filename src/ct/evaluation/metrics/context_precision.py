# context_precision.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ct.evaluation.schemas import ContextPrecisionResponse, MetricScore
from ct.evaluation.utils import format_verbose_log, format_previous_messages
from ct.evaluation.prompts import CONTEXT_PRECISION_PROMPT, CONVERSATION_CONTEXT_BLOCK
import logging

logger = logging.getLogger(__name__)

async def evaluate_context_precision(
    question: str,
    answer: str,
    verbose_log: str,
    llm: ChatOpenAI,
    previous_messages: list[dict] = []
) -> MetricScore:
    
    history_str = format_previous_messages(previous_messages)

    conversation_context = (
        CONVERSATION_CONTEXT_BLOCK.format(previous_messages=history_str)
        if history_str else ""
    )

    prompt = CONTEXT_PRECISION_PROMPT.format(
        question=question,
        verbose_log=format_verbose_log(verbose_log),
        answer=answer,
        conversation_context=conversation_context
    )
    
    structured_llm = llm.with_structured_output(ContextPrecisionResponse)
    
    try:
        response_raw = await structured_llm.ainvoke([
    HumanMessage(content=prompt)
        ])

        if isinstance(response_raw, ContextPrecisionResponse):
            response = response_raw
        else:
            response = ContextPrecisionResponse.model_validate(response_raw)
        
        return MetricScore(
            score=response.score,
            reasoning=response.reasoning,
            details={
                "tools_used": response.tools_used,
                "tools_relevant": response.tools_relevant,
                "tools_irrelevant": response.tools_irrelevant
            }
        )
    except Exception as e:
        logger.error(f"Error evaluando context precision: {e}")
        return MetricScore(
            score=0.5,
            reasoning=f"Error en evaluación: {str(e)}",
            details={}
        )