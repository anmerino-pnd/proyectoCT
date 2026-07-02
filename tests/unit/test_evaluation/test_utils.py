"""
Tests para el pre-procesamiento del evaluador RAGAS.

Verifican que split_answer_blocks separa correctamente la prosa de los
bloques estructurados ```ct-products``` / ```ct-suggestions``` que el
chatbot emite, y que format_product_cards / format_available_tools quedan
alineados con el formato y el toolset actuales.
"""

import pytest


@pytest.mark.unit
class TestSplitAnswerBlocks:
    """Tests para split_answer_blocks."""

    def test_splits_prose_products_and_suggestions(self):
        from ct.evaluation.utils import split_answer_blocks

        answer = (
            "¡Buena elección! Te dejo unas opciones ideales para oficina:\n\n"
            "```ct-products\n"
            '[{"clave":"CPULEN9780","marca":"Lenovo","modelo":"IdeaPad 3",'
            '"precio":12990,"moneda":"MXN","en_su_sucursal":3,'
            '"en_otras_sucursales":12,"en_promocion":true}]\n'
            "```\n\n"
            "Los precios y existencias están sujetos a cambios.\n\n"
            "```ct-suggestions\n"
            '["Muéstrame opciones más económicas","Prefiero marca Lenovo"]\n'
            "```"
        )

        prose, products, suggestions = split_answer_blocks(answer)

        # La prosa no contiene los bloques.
        assert "ct-products" not in prose
        assert "ct-suggestions" not in prose
        assert "Buena elección" in prose
        assert "sujetos a cambios" in prose

        # Los productos se parsean como dicts.
        assert len(products) == 1
        assert products[0]["clave"] == "CPULEN9780"
        assert products[0]["precio"] == 12990
        assert products[0]["en_promocion"] is True

        # Las sugerencias como lista de strings.
        assert suggestions == [
            "Muéstrame opciones más económicas",
            "Prefiero marca Lenovo",
        ]

    def test_malformed_products_json_yields_empty_list(self):
        from ct.evaluation.utils import split_answer_blocks

        answer = "Aquí tienes:\n```ct-products\n[{clave: roto,,}]\n```"

        prose, products, suggestions = split_answer_blocks(answer)

        assert products == []
        assert suggestions == []
        # La prosa sigue limpia aunque el JSON estuviera roto.
        assert "ct-products" not in prose
        assert "Aquí tienes" in prose

    def test_no_blocks_returns_answer_as_prose(self):
        from ct.evaluation.utils import split_answer_blocks

        answer = "Nuestras sucursales abren de 9 a 6 de lunes a viernes."
        prose, products, suggestions = split_answer_blocks(answer)

        assert prose == answer
        assert products == []
        assert suggestions == []

    def test_empty_answer(self):
        from ct.evaluation.utils import split_answer_blocks

        prose, products, suggestions = split_answer_blocks("")
        assert prose == ""
        assert products == []
        assert suggestions == []


@pytest.mark.unit
class TestFormatProductCards:
    """Tests para format_product_cards."""

    def test_renders_factual_fields(self):
        from ct.evaluation.utils import format_product_cards

        cards = [
            {
                "clave": "CPULEN9780",
                "marca": "Lenovo",
                "precio": 12990,
                "moneda": "MXN",
                "en_promocion": True,
            }
        ]
        rendered = format_product_cards(cards)

        assert "CPULEN9780" in rendered
        assert "12990" in rendered
        assert "Lenovo" in rendered
        assert "Tarjeta 1" in rendered

    def test_empty_cards_returns_empty_string(self):
        from ct.evaluation.utils import format_product_cards

        assert format_product_cards([]) == ""


@pytest.mark.unit
class TestFormatAvailableTools:
    """La lista de tools del evaluador debe reflejar el toolset actual."""

    def test_sales_rules_uses_batch_signature(self):
        from ct.evaluation.utils import format_available_tools

        tools = format_available_tools()
        # La firma batch actual usa 'claves=[...]', no 'clave' singular.
        assert "claves=[" in tools

    def test_lists_the_seven_registered_tools(self):
        from ct.evaluation.utils import format_available_tools

        tools = format_available_tools()
        for name in (
            "algolia_search_tool",
            "sales_rules_tool",
            "dolar_convertion_tool",
            "status_tool",
            "get_support_info",
            "who_are_we",
            "get_sucursales_info",
        ):
            assert name in tools
