import os
import time
import json


class ChatHistoryManager:
    def __init__(self, history_file=r"C:\Users\angel.merino\Documents\proyectoCT\datos\chat_history.json"):
        self.history_file = history_file
        self._ensure_history_file()
        self.histories = self.load_history()

    def _ensure_history_file(self):
        """Verifica si el archivo de historial existe, si no, lo crea vacío."""
        if not os.path.exists(self.history_file):
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)

    def load_history(self):
        """Carga el historial de conversaciones desde un archivo JSON."""
        with open(self.history_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_history(self):
        """Guarda el historial actualizado en el archivo JSON."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.histories, f, indent=4, ensure_ascii=False)


    def add_message(self, session_id: str, message_type: str, content: str, metadata: dict = None):
        """Versión mejorada que soporta metadata."""
        if session_id not in self.histories:
            self.histories[session_id] = []

        match message_type:
            case "human":
                message = {
                    "type": "human",
                    "content": content,
                    "timestamp": time.time()
                }
            case "system":
                message = {
                    "type": "system",
                    "content": content,
                    "timestamp": time.time(),
                    "metadata": metadata if metadata else {}
                }
            case _:
                raise ValueError("Invalid message type. Use 'human' or 'system'.")
        
        self.histories[session_id].append(message)

        self.save_history()
