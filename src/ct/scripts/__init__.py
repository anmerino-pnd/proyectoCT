"""Scripts utilitarios y de preprocesamiento (ETL/scraping/imágenes) que NO forman
parte del runtime del chatbot ni del conjunto de tools del agente.

Se ejecutan manualmente. Se separaron de `ct.tools` (que contiene únicamente las
herramientas que el agente LLM invoca) para mantener limpio el grafo de dependencias
del servicio.
"""
