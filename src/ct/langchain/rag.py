from ct.clients import openai_api_key
from langchain_openai import OpenAIEmbeddings
from ct.langchain.assistant import LangchainAssistant
from ct.langchain.vectorstore import LangchainVectorStore
from typing import AsyncGenerator
from ct.langchain.tool_agent import ToolAgent
from ct.moderation.query_moderator import QueryModerator

class LangchainRAG:
    def __init__(self, index_path: str = None):
        self.embedder = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.vectorstore = LangchainVectorStore(self.embedder, index_path)
        
        # Verifica que el retriever se haya creado
        if not hasattr(self.vectorstore, 'retriever'):
            raise ValueError("VectorStore no se inicializó correctamente. ¿El índice existe?")
            
        self.assistant = LangchainAssistant(self.vectorstore.retriever)
        self.tool_agent = ToolAgent(self.assistant)
        self.moderator = QueryModerator(assistant=self.assistant)


    async def run(self, query: str, session_id: str = None, listaPrecio : str = None) -> AsyncGenerator[str, None]:
        """Ejecuta una consulta RAG y muestra los chunks de respuesta en tiempo real."""

        session = self.assistant.ensure_session(session_id)
        ban_message = self.moderator.check_if_banned(session)
        if ban_message:
            yield ban_message
            return

        label = self.moderator.classify_query(query).strip().lower()

        if label == "relevante":
            label_relevant = self.moderator.classify_relevant_query(query).strip().lower()
            print(label_relevant)
            if label_relevant == 'existencias':
                async for chunk in self.tool_agent.run_existencias(query, session_id):
                    yield chunk
            elif label_relevant == 'informacion':
                async for chunk in self.assistant.answer(session_id, query, listaPrecio):
                    yield chunk
            else:
                async for chunk in self.assistant.answer(session_id, query, listaPrecio):
                    yield chunk
        elif label == "irrelevante":
            answer = self.moderator.polite_answer()
            self.assistant.add_irrelevant_message(session_id=session_id, question=query, full_answer=answer)
            yield answer
        elif label == "inapropiado":
            session = self.assistant.sessions.find_one({"session_id": session_id}) or {}
            msg, tries, banned_until = self.moderator.evaluate_inappropriate_behavior(session, query)

            self.moderator.update_inappropriate_session(session_id, tries, banned_until)
            yield msg
        else:
            yield "Lo siento, no entendí tu mensaje. ¿Podrías reformularlo?"

