"""Claude-powered free-text handling with tool use for the meal bot."""

import asyncio
import json
from datetime import date

import anthropic

import anytype_api
import meal_planner
from bot_handlers import SPACE_ID

from telegram import Update
from telegram.ext import ContextTypes

MODEL = "claude-sonnet-4-20250514"
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """You are a meal planning assistant. You manage recipes and weekly dinner plans \
stored in Anytype. Check existing recipes before creating new ones. \
Keep responses concise and friendly. Current date: {today}"""

TOOLS = [
    {
        "name": "list_recipes",
        "description": "List all recipes with names and descriptions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recipe",
        "description": "Get full details of a recipe by name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Recipe name"}},
            "required": ["name"],
        },
    },
    {
        "name": "create_recipe",
        "description": "Create a new recipe in Anytype.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "ingredients": {"type": "array", "items": {"type": "string"}},
                "instructions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "ingredients", "instructions"],
        },
    },
    {
        "name": "get_current_plan",
        "description": "Get this week's day-by-day meal plan.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "plan_week",
        "description": "Generate a new random 7-day meal plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recipe names to exclude",
                },
            },
            "required": [],
        },
    },
    {
        "name": "swap_meal",
        "description": "Replace one day's meal in the current plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {"type": "string", "description": "Day name (e.g. Monday, tue)"},
                "recipe_name": {"type": "string", "description": "Optional: specific recipe to use"},
            },
            "required": ["day"],
        },
    },
    {
        "name": "get_shopping_list",
        "description": "Get an aggregated shopping list from this week's plan.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _all_recipes() -> list[dict]:
    objects = anytype_api.search_objects(SPACE_ID)
    return meal_planner.filter_recipes(objects)


def _all_meal_plans() -> list[dict]:
    objects = anytype_api.search_objects(SPACE_ID)
    return meal_planner.filter_meal_plans(objects)


def _current_plan() -> dict | None:
    target = meal_planner.current_week_plan_name()
    for p in _all_meal_plans():
        if p.get("name") == target:
            return p
    return None


def _plan_to_recipes(plan_obj: dict, recipes: list[dict]) -> list[dict]:
    body = plan_obj.get("markdown", "") or plan_obj.get("body", "")
    names = meal_planner.parse_plan_body(body)
    recipe_map = {r["name"].lower(): r for r in recipes}
    return [recipe_map.get(n.lower(), {"name": n}) for n in names]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call to the appropriate function. Returns JSON string."""
    if tool_name == "list_recipes":
        recipes = _all_recipes()
        summaries = [{"name": r["name"], "description": r.get("snippet", "")} for r in recipes]
        return json.dumps(summaries)

    if tool_name == "get_recipe":
        name = tool_input["name"]
        for r in _all_recipes():
            if r["name"].lower() == name.lower():
                return json.dumps({
                    "name": r["name"],
                    "description": r.get("snippet", ""),
                    "body": r.get("markdown", "") or r.get("body", ""),
                })
        return json.dumps({"error": f"Recipe '{name}' not found"})

    if tool_name == "create_recipe":
        body = meal_planner.build_recipe_body(
            tool_input["name"],
            tool_input["ingredients"],
            tool_input["instructions"],
        )
        result = anytype_api.create_object(
            SPACE_ID, "recipe", tool_input["name"],
            body=body,
            description=tool_input.get("description", ""),
            icon={"format": "emoji", "emoji": "\U0001F373"},
        )
        obj = result.get("object", {})
        return json.dumps({"created": obj.get("name", tool_input["name"])})

    if tool_name == "get_current_plan":
        plan = _current_plan()
        if not plan:
            return json.dumps({"error": "No plan for this week"})
        recipes = _all_recipes()
        recipe_list = _plan_to_recipes(plan, recipes)
        monday = meal_planner.current_week_monday()
        return json.dumps({
            "name": plan["name"],
            "plan": meal_planner.format_plan_message(recipe_list, monday.isoformat()),
        })

    if tool_name == "plan_week":
        recipes = _all_recipes()
        if not recipes:
            return json.dumps({"error": "No recipes found"})
        exclude = tool_input.get("exclude", [])
        plan = meal_planner.pick_weekly_plan(recipes, exclude_names=exclude)
        monday = meal_planner.current_week_monday()
        start_date = monday.isoformat()
        plan_name = meal_planner.current_week_plan_name()
        body = meal_planner.build_plan_body(plan, start_date)

        existing = _current_plan()
        if existing:
            anytype_api.update_object(SPACE_ID, existing["id"], body=body)
        else:
            anytype_api.create_object(SPACE_ID, "meal_plan", plan_name, body=body)

        return json.dumps({
            "plan": meal_planner.format_plan_message(plan, start_date),
        })

    if tool_name == "swap_meal":
        day_index = meal_planner.day_name_to_index(tool_input["day"])
        if day_index is None:
            return json.dumps({"error": f"Unknown day: {tool_input['day']}"})
        plan_obj = _current_plan()
        if not plan_obj:
            return json.dumps({"error": "No plan for this week"})
        recipes = _all_recipes()
        recipe_list = _plan_to_recipes(plan_obj, recipes)
        if day_index >= len(recipe_list):
            return json.dumps({"error": "Plan doesn't have that many days"})

        # If a specific recipe is requested, find it
        requested = tool_input.get("recipe_name")
        if requested:
            match = None
            for r in recipes:
                if r["name"].lower() == requested.lower():
                    match = r
                    break
            if match:
                new_plan = list(recipe_list)
                new_plan[day_index] = match
            else:
                return json.dumps({"error": f"Recipe '{requested}' not found"})
        else:
            new_plan = meal_planner.swap_day(recipe_list, day_index, recipes)

        monday = meal_planner.current_week_monday()
        body = meal_planner.build_plan_body(new_plan, monday.isoformat())
        anytype_api.update_object(SPACE_ID, plan_obj["id"], body=body)
        day_name = meal_planner.DAY_NAMES[day_index]
        return json.dumps({"swapped": day_name, "new_recipe": new_plan[day_index].get("name")})

    if tool_name == "get_shopping_list":
        plan_obj = _current_plan()
        if not plan_obj:
            return json.dumps({"error": "No plan for this week"})
        recipes = _all_recipes()
        recipe_list = _plan_to_recipes(plan_obj, recipes)
        full = [r for r in recipe_list if r.get("markdown") or r.get("body")]
        ingredients = meal_planner.aggregate_shopping_list(full)
        return json.dumps({"ingredients": ingredients})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def chat(user_message: str, conversation_history: list[dict], client: anthropic.Anthropic) -> tuple[str, list[dict]]:
    """Run the Claude agent loop. Returns (response_text, updated_history)."""
    system = SYSTEM_PROMPT.format(today=date.today().isoformat())
    conversation_history = list(conversation_history)
    conversation_history.append({"role": "user", "content": user_message})

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=conversation_history,
        )

        # Collect text and tool use blocks
        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        # If no tool calls, we're done
        if not tool_calls:
            assistant_text = "\n".join(text_parts) or "I'm not sure how to help with that."
            conversation_history.append({"role": "assistant", "content": response.content})
            return assistant_text, conversation_history

        # Execute tool calls and build tool results
        conversation_history.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tc in tool_calls:
            result = execute_tool(tc.name, tc.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })
        conversation_history.append({"role": "user", "content": tool_results})

    # Safety cutoff
    return "I've been working on this for a while. Let me summarize what I've done so far.", conversation_history


# --- Telegram integration ---

_conversations: dict[int, list[dict]] = {}
_MAX_HISTORY = 20
_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command text messages via Claude."""
    user_id = update.effective_user.id
    history = _conversations.get(user_id, [])

    text, new_history = await asyncio.to_thread(
        chat, update.message.text, history, _get_client()
    )

    # Trim history to last N messages
    if len(new_history) > _MAX_HISTORY:
        new_history = new_history[-_MAX_HISTORY:]
    _conversations[user_id] = new_history

    await update.message.reply_text(text)
