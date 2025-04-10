from string import Template
from typing import AsyncGenerator
from ct.retriever import VectorStore
from ct.llm_types import LLMAPIResponseError
from ct.history import ChatHistoryManager
from langchain.schema import AIMessage, HumanMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain, create_history_aware_retriever

class RAGassistant(VectorStore):
    def __init__(self, llm, VECTOR_DB_PATH, embedding_model):
        # Inicializar primero VectorStore para que `VECTOR_DB_PATH` esté disponible
        super().__init__(VECTOR_DB_PATH, embedding_model)

        self.llm = llm
        self.histories = self.histories = ChatHistoryManager().histories
        self.retriever = self.asRetriever()  


    def offer_history_prompt(self) -> str:
        return (
            "Dada una historia de chat y la última pregunta del usuario "
            "que podría hacer referencia al contexto en la historia de chat, "
            "formula una pregunta independiente que pueda ser entendida "
            "sin la historia de chat. NO respondas la pregunta, "
            "solo reformúlala si es necesario y, en caso contrario, devuélvela tal como está." 
        )

    def QpromptTemplate(self):
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.offer_history_prompt()),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

    def offer_user(self) -> str:
        tpl = (
        """
        Basate solo en los siguientes fragmentos de contexto para responder la consulta del usuario.  

        El usuario pertenece a la listaPrecio {listaPrecio}, así que usa exclusivamente los precios de esta lista. 
        No menciones la lista de precios en la respuesta, solo proporciona el precio final en formato de precio (por ejemplo, $1,000.00).  

        Si hay productos en oferta, menciónalos primero. 
        Si no hay promociones, ofrece los productos normales con su precio correcto.  
        Si el usuario pregunta por un producto específico, verifica si está en promoción y notifícalo.  

        Para que un producto se considere en promoción debe tener las variables de precio_oferta, descuento, EnCompraDE y Unidades.
        Luego, estas deben cumplir las siguientes condiciones:

        1. Si el producto tiene un precio_oferta mayor a 0.0:  
            - Usa este valor como el precio final y ofrécelo al usuario. 

        2. Si el precio_oferta es 0, pero el descuento es mayor a 0.0%:  
            - Aplica el descuento al precio que se encuentra en lista_precios y toma el precio correspondiente a la listaPrecio {listaPrecio}.  
            - Muestra ese precio tachado y el nuevo precio con el descuento aplicado.  

        3. Si el precio_oferta y el descuento son 0.0, pero la variable EnCompraDE es mayor a 0 y Unidades es mayor a 0:  
            - Menciona que hay una promoción especial al comprar cierta cantidad.  
            - Usa un tono sutil, por ejemplo: "En compra de 'X' productos, recibirás 'Y' unidades gratis."  

        Revisa también:  
            - La variable limitadoA para indicar si la disponibilidad es limitada.  
            - La variable fecha_fin para aclarar la vigencia de la promoción.  

        Formato de respuesta, SIEMPRE:  
        - Para cada producto que ofrezcas:
            * Toma la 'clave' del producto
            * Resalta el nombre poniendo su hipervinculo https://ctonline.mx/buscar/productos?b=clave
        - Presenta la información de manera clara
        - Los detalles y precios puntualizados y estructurados 
        - Espacios entre productos.         
        - Evita explicaciones largas o innecesarias.  

        Siempre aclara al final que la disponibilidad y los precios pueden cambiar.  

        Contexto: {context}  
        """
            )
    
        return tpl



    def QApromptTemplate(self):
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.offer_user()),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
    
    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """Obtiene el historial de una sesión específica y lo convierte en BaseChatMessageHistory."""
        if session_id not in self.histories:
            self.histories[session_id] = []

        messages = [
            HumanMessage(content=m["content"]) if m["type"] == "human" else AIMessage(content=m["content"])
            for m in self.histories[session_id]
        ]
        return ChatMessageHistory(messages=messages)
       
    def build_chain(self):
        history_aware_retriever = create_history_aware_retriever(self.llm, self.retriever, self.QpromptTemplate())
        question_answer_chain = create_stuff_documents_chain(self.llm, self.QApromptTemplate())
        return create_retrieval_chain(history_aware_retriever, question_answer_chain)

    def build_conversational_chain(self) -> RunnableWithMessageHistory:
        rag_chain = self.build_chain()
        return RunnableWithMessageHistory(
            rag_chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer"
        )
  
    async def async_prompt(self, user_enquery: str, user_id: str, listaPrecio: str, callbacks= None) -> AsyncGenerator[str, None]:
        try:
            config = {"configurable": {"session_id": user_id}}
            if callbacks:
                config["callbacks"] = callbacks if isinstance(callbacks, list) else [callbacks]
                async for chunk in self.build_conversational_chain().astream(
                    {"input": user_enquery, "listaPrecio": listaPrecio}, 
                    config=config
                ):
                    yield chunk
        except Exception as e:
            raise LLMAPIResponseError(response=None, message="Error al invocar el modelo LLM.", exception=e)
        