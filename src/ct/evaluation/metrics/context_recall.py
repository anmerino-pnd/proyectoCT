from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ct.evaluation.schemas import ContextRecallResponse, MetricScore
from ct.evaluation.prompts import CONTEXT_RECALL_PROMPT
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


def extract_tool_names_list(verbose_log: str) -> list[str]:
    if not verbose_log:
        return []
    
    lines = verbose_log.split("\n")
    tools = []
    
    for line in lines:
        if "decidió usar:" in line:
            tool_name = line.split("decidió usar:")[-1].strip()
            tools.append(tool_name)
    
    return list(set(tools))  # Únicos


async def evaluate_context_recall(
    question: str,
    answer: str,
    verbose_log: str,
    llm: ChatOpenAI
) -> MetricScore:
    
    tools_used = extract_tool_names_list(verbose_log)
    
    prompt = CONTEXT_RECALL_PROMPT.format(
        question=question,
        available_tools="\n".join([f"- {t}" for t in AVAILABLE_TOOLS]),
        tools_used=", ".join(tools_used) if tools_used else "Ninguna",
        answer=answer
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