# faithfulness.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ct.evaluation.schemas import FaithfulnessResponse, MetricScore
from ct.evaluation.prompts import FAITHFULNESS_PROMPT, CONVERSATION_CONTEXT_BLOCK
from ct.evaluation.utils import format_verbose_log, format_previous_messages 
import logging

logger = logging.getLogger(__name__)


async def evaluate_faithfulness(
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

    prompt = FAITHFULNESS_PROMPT.format(
        question=question,
        verbose_log=format_verbose_log(verbose_log),  
        answer=answer,
        conversation_context=conversation_context
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