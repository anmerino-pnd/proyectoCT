from typing import AsyncGenerator
from ct.settings.cache import set_llm_cache
from ct.langchain.tool_agent import ToolAgent
from ct.moderation.query_moderator import QueryModerator


class ModeratedToolAgent:
    def __init__(self):
        self.tool_agent = ToolAgent()
        self.moderator = QueryModerator(assistant=self.tool_agent)


    async def run(self, query: str, session_id: str = None, listaPrecio : str = None) -> AsyncGenerator[str, None]:
        """Ejecuta una consulta RAG y muestra los chunks de respuesta en tiempo real."""

        session = self.tool_agent.ensure_session(session_id)
        ban_message = self.moderator.check_if_banned(session)
        if ban_message:
            yield ban_message
            return

        label = self.moderator.classify_query(query, session_id=session_id).strip().lower()

        if label == "relevante":
            async for chunk in self.tool_agent.run(query, session_id, lista_precio=listaPrecio):
                yield chunk
        elif label == "irrelevante":
            answer = self.moderator.polite_answer()
            self.tool_agent.add_irrelevant_message(session_id=session_id, question=query, full_answer=answer)
            yield answer
        elif label == "inapropiado":
            session = self.tool_agent.sessions.find_one({"session_id": session_id}) or {}
            msg, tries, banned_until = self.moderator.evaluate_inappropriate_behavior(session, query)

            self.moderator.update_inappropriate_session(session_id, tries, banned_until)
            yield msg
        else:
            yield "Lo siento, no entendí tu mensaje. ¿Podrías reformularlo?"

