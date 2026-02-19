"""Tests for bot_handlers — mocked Anytype API calls."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

import meal_planner


def _recipe(name, body=""):
    return {
        "object": "object",
        "id": f"id-{name.lower().replace(' ', '-')}",
        "name": name,
        "type": {"object": "type", "key": "recipe", "name": "Recipe"},
        "snippet": "",
        "markdown": body,
    }


def _meal_plan(name, body=""):
    return {
        "object": "object",
        "id": f"id-{name.lower().replace(' ', '-')}",
        "name": name,
        "type": {"object": "type", "key": "meal_plan", "name": "Meal Plan"},
        "markdown": body,
    }


def _make_update_context(args=None):
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 12345
    ctx = MagicMock()
    ctx.args = args or []
    return update, ctx


RECIPES = [_recipe("Oats"), _recipe("Pasta"), _recipe("Stir-Fry")]


@pytest.fixture
def mock_api():
    with patch("bot_handlers.anytype_api") as api:
        api.search_objects.return_value = RECIPES
        api.create_object.return_value = {"object": {"name": "Test"}}
        api.update_object.return_value = {}
        yield api


@pytest.mark.asyncio
async def test_recipes_lists_all(mock_api):
    from bot_handlers import recipes
    update, ctx = _make_update_context()
    await recipes(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "Oats" in reply
    assert "Pasta" in reply
    assert "Stir-Fry" in reply


@pytest.mark.asyncio
async def test_plan_week_creates_plan(mock_api):
    from bot_handlers import plan_week
    update, ctx = _make_update_context()

    # Need enough recipes for 7 days - add more
    many_recipes = [_recipe(f"R{i}") for i in range(10)]
    mock_api.search_objects.return_value = many_recipes

    await plan_week(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "Meal plan" in reply
    # Should have created a meal plan object
    mock_api.create_object.assert_called_once()


@pytest.mark.asyncio
async def test_plan_week_no_recipes(mock_api):
    from bot_handlers import plan_week
    update, ctx = _make_update_context()
    mock_api.search_objects.return_value = []
    await plan_week(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "No recipes" in reply


@pytest.mark.asyncio
async def test_add_recipe(mock_api):
    from bot_handlers import add_recipe
    update, ctx = _make_update_context(args=["Banana", "Pancakes"])
    await add_recipe(update, ctx)
    mock_api.create_object.assert_called_once()
    call_args = mock_api.create_object.call_args
    assert call_args[0][2] == "Banana Pancakes"  # name


@pytest.mark.asyncio
async def test_add_recipe_no_args(mock_api):
    from bot_handlers import add_recipe
    update, ctx = _make_update_context()
    await add_recipe(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "Usage" in reply


@pytest.mark.asyncio
async def test_whats_for_dinner_no_plan(mock_api):
    from bot_handlers import whats_for_dinner
    update, ctx = _make_update_context()
    # No meal plans in search results
    mock_api.search_objects.return_value = RECIPES  # only recipes, no plans
    await whats_for_dinner(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "No meal plan" in reply


@pytest.mark.asyncio
async def test_swap_bad_day(mock_api):
    from bot_handlers import swap
    update, ctx = _make_update_context(args=["badday"])
    await swap(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "Unknown day" in reply


@pytest.mark.asyncio
async def test_swap_no_args(mock_api):
    from bot_handlers import swap
    update, ctx = _make_update_context()
    await swap(update, ctx)
    reply = update.message.reply_text.call_args[0][0]
    assert "Usage" in reply
