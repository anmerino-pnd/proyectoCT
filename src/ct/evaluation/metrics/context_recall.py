# context_recall.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ct.evaluation.schemas import ContextRecallResponse, MetricScore
from ct.evaluation.prompts import CONTEXT_RECALL_PROMPT, CONVERSATION_CONTEXT_BLOCK
from ct.evaluation.utils import format_verbose_log, format_previous_messages, format_available_tools
import logging

logger = logging.getLogger(__name__)

async def evaluate_context_recall(
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

    prompt = CONTEXT_RECALL_PROMPT.format(
        question=question,
        verbose_log=format_verbose_log(verbose_log),
        available_tools=format_available_tools(),
        answer=answer,
        conversation_context=conversation_context
    )
    
    structured_llm = llm.with_structured_output(ContextRecallResponse)
    
    try:
        response_raw = await structured_llm.ainvoke([
    HumanMessage(content=prompt)
        ])

        if isinstance(response_raw, ContextRecallResponse):
            response = response_raw
        else:
            response = ContextRecallResponse.model_validate(response_raw)
        
        return MetricScore(
            score=response.score,
            reasoning=response.reasoning,
            details={
                "missing_tools": response.missing_tools,
                "coverage": response.coverage
            }
        )
    except Exception as e:
        logger.error(f"Error evaluando context recall: {e}")
        return MetricScore(
            score=0.5,
            reasoning=f"Error en evaluación: {str(e)}",
            details={}
        )