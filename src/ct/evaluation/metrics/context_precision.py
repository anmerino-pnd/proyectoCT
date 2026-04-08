from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ct.evaluation.schemas import ContextPrecisionResponse, MetricScore
from ct.evaluation.prompts import CONTEXT_PRECISION_PROMPT
import logging

logger = logging.getLogger(__name__)


AVAILABLE_TOOLS = [
    "algolia_search_tool",
    "sales_rules_tool", 
    "dolar_convertion_tool",
    "status_tool",
    "get_support_info",
    "who_are_we",
    "get_sucursales_info"
]


def extract_tools_with_args(verbose_log: str) -> str:
    """Extrae tools usadas con sus argumentos."""
    if not verbose_log:
        return "Ninguna"
    
    lines = verbose_log.split("\n")
    result = []
    current_tool = None
    
    for line in lines:
        if "decidió usar:" in line:
            current_tool = line.split("decidió usar:")[-1].strip()
        elif line.strip().startswith("Args:") and current_tool:
            result.append(f"- {current_tool}: {line.strip()}")
            current_tool = None
    
    return "\n".join(result) if result else "Ninguna"


async def evaluate_context_precision(
    question: str,
    answer: str,
    verbose_log: str,
    llm: ChatOpenAI
) -> MetricScore:
    
    tools_used = extract_tools_with_args(verbose_log)
    
    prompt = CONTEXT_PRECISION_PROMPT.format(
        question=question,
        available_tools=", ".join(AVAILABLE_TOOLS),
        tools_used_with_args=tools_used,
        answer=answer
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