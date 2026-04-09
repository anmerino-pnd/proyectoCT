# answer_relevancy.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ct.evaluation.schemas import AnswerRelevancyResponse, MetricScore
from ct.evaluation.prompts import ANSWER_RELEVANCY_PROMPT, CONVERSATION_CONTEXT_BLOCK
from ct.evaluation.utils import format_verbose_log, format_previous_messages
import logging

logger = logging.getLogger(__name__)



async def evaluate_answer_relevancy(
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

    prompt = ANSWER_RELEVANCY_PROMPT.format(
        question=question,
        answer=answer,
        verbose_log=format_verbose_log(verbose_log),
        conversation_context=conversation_context
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