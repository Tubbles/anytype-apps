"""Telegram command handlers — thin async layer over meal_planner + anytype_api."""

import asyncio
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

import anytype_api
import meal_planner

SPACE_ID = "bafyreicqqydmxrx4a2huxxcxome4vq3ovn3lgdxvdy7ktiyp5xh5ld4bxq.1tgkqb3hjg356"


def _fetch_all_objects() -> list[dict]:
    return anytype_api.search_objects(SPACE_ID)


def _fetch_all_recipes() -> list[dict]:
    return meal_planner.filter_recipes(_fetch_all_objects())


def _fetch_all_meal_plans() -> list[dict]:
    return meal_planner.filter_meal_plans(_fetch_all_objects())


def _find_current_plan(plans: list[dict]) -> dict | None:
    """Find this week's meal plan by name."""
    target = meal_planner.current_week_plan_name()
    for p in plans:
        if p.get("name") == target:
            return p
    return None


def _plan_to_recipe_list(plan_obj: dict, all_recipes: list[dict]) -> list[dict]:
    """Convert a meal plan object to a list of recipe dicts by matching names."""
    body = plan_obj.get("markdown", "") or plan_obj.get("body", "")
    names = meal_planner.parse_plan_body(body)
    recipe_map = {r["name"].lower(): r for r in all_recipes}
    return [recipe_map.get(n.lower(), {"name": n}) for n in names]


async def plan_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a new weekly meal plan."""
    recipes = await asyncio.to_thread(_fetch_all_recipes)
    if not recipes:
        await update.message.reply_text("No recipes found. Add some first!")
        return

    exclude = []
    if context.args:
        exclude = context.args

    plan = meal_planner.pick_weekly_plan(recipes, exclude_names=exclude)
    monday = meal_planner.current_week_monday()
    start_date = monday.isoformat()
    plan_name = meal_planner.current_week_plan_name()
    body = meal_planner.build_plan_body(plan, start_date)

    # Check if plan already exists, update or create
    plans = await asyncio.to_thread(_fetch_all_meal_plans)
    existing = _find_current_plan(plans)
    if existing:
        await asyncio.to_thread(
            anytype_api.update_object, SPACE_ID, existing["id"], body=body
        )
    else:
        await asyncio.to_thread(
            anytype_api.create_object, SPACE_ID, "meal_plan", plan_name, body=body
        )

    msg = meal_planner.format_plan_message(plan, start_date)
    await update.message.reply_text(msg)


async def whats_for_dinner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's planned meal."""
    plans = await asyncio.to_thread(_fetch_all_meal_plans)
    recipes = await asyncio.to_thread(_fetch_all_recipes)
    current = _find_current_plan(plans)
    if not current:
        await update.message.reply_text("No meal plan for this week. Use /plan_week to create one.")
        return

    recipe_list = _plan_to_recipe_list(current, recipes)
    today_weekday = date.today().weekday()
    recipe = meal_planner.todays_meal(recipe_list, today_weekday)
    if recipe:
        day_name = meal_planner.DAY_NAMES[today_weekday]
        await update.message.reply_text(f"{day_name}'s dinner: {recipe.get('name', 'Unknown')}")
    else:
        await update.message.reply_text("No meal planned for today.")


async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a shopping list from the current week's plan."""
    plans = await asyncio.to_thread(_fetch_all_meal_plans)
    recipes = await asyncio.to_thread(_fetch_all_recipes)
    current = _find_current_plan(plans)
    if not current:
        await update.message.reply_text("No meal plan for this week. Use /plan_week to create one.")
        return

    recipe_list = _plan_to_recipe_list(current, recipes)
    # Only include recipes that have markdown (real recipe objects)
    full_recipes = [r for r in recipe_list if r.get("markdown") or r.get("body")]
    ingredients = meal_planner.aggregate_shopping_list(full_recipes)
    if not ingredients:
        await update.message.reply_text("No ingredients found in this week's recipes.")
        return

    msg = meal_planner.format_shopping_list_message(ingredients)
    await update.message.reply_text(msg)


async def add_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new recipe by name. Usage: /add_recipe Banana Pancakes"""
    if not context.args:
        await update.message.reply_text("Usage: /add_recipe Recipe Name")
        return

    name = " ".join(context.args)
    await asyncio.to_thread(
        anytype_api.create_object, SPACE_ID, "recipe", name,
        icon={"format": "emoji", "emoji": "\U0001F373"},
    )
    await update.message.reply_text(f"Created recipe: {name}\nEdit it in Anytype to add ingredients and instructions.")


async def recipes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all recipes."""
    all_recipes = await asyncio.to_thread(_fetch_all_recipes)
    msg = meal_planner.format_recipes_list_message(all_recipes)
    await update.message.reply_text(msg)


async def swap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Swap a day's meal. Usage: /swap tuesday"""
    if not context.args:
        await update.message.reply_text("Usage: /swap <day> [exclude1 exclude2 ...]")
        return

    day_str = context.args[0]
    day_index = meal_planner.day_name_to_index(day_str)
    if day_index is None:
        await update.message.reply_text(f"Unknown day: {day_str}")
        return

    exclude = context.args[1:] if len(context.args) > 1 else []

    plans = await asyncio.to_thread(_fetch_all_meal_plans)
    all_recipes = await asyncio.to_thread(_fetch_all_recipes)
    current = _find_current_plan(plans)
    if not current:
        await update.message.reply_text("No meal plan for this week. Use /plan_week to create one.")
        return

    recipe_list = _plan_to_recipe_list(current, all_recipes)
    if day_index >= len(recipe_list):
        await update.message.reply_text("Plan doesn't have that many days.")
        return

    new_plan = meal_planner.swap_day(recipe_list, day_index, all_recipes, exclude_names=exclude)
    monday = meal_planner.current_week_monday()
    body = meal_planner.build_plan_body(new_plan, monday.isoformat())
    await asyncio.to_thread(
        anytype_api.update_object, SPACE_ID, current["id"], body=body
    )

    day_name = meal_planner.DAY_NAMES[day_index]
    new_recipe = new_plan[day_index]
    await update.message.reply_text(f"Swapped {day_name} to: {new_recipe.get('name', 'Unknown')}")
