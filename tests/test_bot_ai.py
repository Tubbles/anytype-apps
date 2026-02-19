"""Tests for bot_ai — mocked Claude API and Anytype calls."""

import json
import pytest
from unittest.mock import MagicMock, patch

from bot_ai import chat, execute_tool


def _recipe(name, body=""):
    return {
        "object": "object",
        "id": f"id-{name.lower().replace(' ', '-')}",
        "name": name,
        "type": {"object": "type", "key": "recipe", "name": "Recipe"},
        "snippet": f"Desc of {name}",
        "markdown": body,
    }


def _meal_plan(name, body=""):
    return {
        "object": "object",
        "id": f"id-plan",
        "name": name,
        "type": {"object": "type", "key": "meal_plan", "name": "Meal Plan"},
        "markdown": body,
    }


RECIPES = [
    _recipe("Oats", "## Ingredients\n- Oats\n- Milk\n\n## Instructions\n1. Mix\n"),
    _recipe("Pasta", "## Ingredients\n- Pasta\n- Sauce\n\n## Instructions\n1. Cook\n"),
]


# --- execute_tool tests ---

class TestExecuteTool:
    @patch("bot_ai.anytype_api")
    def test_list_recipes(self, mock_api):
        mock_api.search_objects.return_value = RECIPES
        result = json.loads(execute_tool("list_recipes", {}))
        assert len(result) == 2
        assert result[0]["name"] == "Oats"

    @patch("bot_ai.anytype_api")
    def test_get_recipe_found(self, mock_api):
        mock_api.search_objects.return_value = RECIPES
        result = json.loads(execute_tool("get_recipe", {"name": "Oats"}))
        assert result["name"] == "Oats"
        assert "Ingredients" in result["body"]

    @patch("bot_ai.anytype_api")
    def test_get_recipe_not_found(self, mock_api):
        mock_api.search_objects.return_value = RECIPES
        result = json.loads(execute_tool("get_recipe", {"name": "Nope"}))
        assert "error" in result

    @patch("bot_ai.anytype_api")
    def test_create_recipe(self, mock_api):
        mock_api.create_object.return_value = {"object": {"name": "New"}}
        result = json.loads(execute_tool("create_recipe", {
            "name": "New",
            "description": "Desc",
            "ingredients": ["A", "B"],
            "instructions": ["Step 1"],
        }))
        assert result["created"] == "New"
        mock_api.create_object.assert_called_once()

    @patch("bot_ai.anytype_api")
    def test_get_current_plan_none(self, mock_api):
        mock_api.search_objects.return_value = RECIPES  # no plans
        result = json.loads(execute_tool("get_current_plan", {}))
        assert "error" in result

    @patch("bot_ai.anytype_api")
    def test_get_shopping_list(self, mock_api):
        from meal_planner import current_week_plan_name, current_week_monday
        plan_name = current_week_plan_name()
        monday = current_week_monday().isoformat()
        plan_body = f"Monday {current_week_monday().month}/{current_week_monday().day}: Oats\nTuesday: Pasta\n"
        objects = RECIPES + [_meal_plan(plan_name, plan_body)]
        mock_api.search_objects.return_value = objects
        result = json.loads(execute_tool("get_shopping_list", {}))
        assert "ingredients" in result
        assert "Oats" in result["ingredients"]

    def test_unknown_tool(self):
        result = json.loads(execute_tool("nonexistent", {}))
        assert "error" in result


# --- chat() tests ---

def _text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_block(tool_id, name, input_data):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_data
    return block


class TestChat:
    def test_simple_text_response(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [_text_block("Hello!")]
        client.messages.create.return_value = response

        text, history = chat("Hi", [], client)
        assert text == "Hello!"
        assert len(history) == 2  # user + assistant

    @patch("bot_ai.execute_tool")
    def test_single_tool_call(self, mock_exec):
        mock_exec.return_value = json.dumps([{"name": "Oats"}])

        client = MagicMock()
        # First call: tool use
        tool_response = MagicMock()
        tool_response.content = [_tool_block("t1", "list_recipes", {})]
        # Second call: text
        text_response = MagicMock()
        text_response.content = [_text_block("Here are your recipes: Oats")]

        client.messages.create.side_effect = [tool_response, text_response]

        text, history = chat("What recipes do we have?", [], client)
        assert "Oats" in text
        mock_exec.assert_called_once_with("list_recipes", {})

    @patch("bot_ai.execute_tool")
    def test_max_tool_rounds_cutoff(self, mock_exec):
        mock_exec.return_value = json.dumps({"result": "ok"})

        client = MagicMock()
        # Always return tool calls, never text
        tool_response = MagicMock()
        tool_response.content = [_tool_block("t1", "list_recipes", {})]
        client.messages.create.return_value = tool_response

        text, history = chat("Loop forever", [], client)
        assert "while" in text.lower()  # safety message
        assert client.messages.create.call_count == 5  # MAX_TOOL_ROUNDS

    @patch("bot_ai.execute_tool")
    def test_multi_step_tool_chain(self, mock_exec):
        mock_exec.side_effect = [
            json.dumps([{"name": "Oats"}, {"name": "Pasta"}]),
            json.dumps({"name": "Oats", "body": "## Ingredients\n- Oats\n"}),
        ]

        client = MagicMock()
        # Step 1: list recipes
        r1 = MagicMock()
        r1.content = [_tool_block("t1", "list_recipes", {})]
        # Step 2: get specific recipe
        r2 = MagicMock()
        r2.content = [_tool_block("t2", "get_recipe", {"name": "Oats"})]
        # Step 3: text response
        r3 = MagicMock()
        r3.content = [_text_block("Oats has oats and milk.")]

        client.messages.create.side_effect = [r1, r2, r3]

        text, history = chat("Tell me about oats", [], client)
        assert "Oats" in text
        assert mock_exec.call_count == 2
