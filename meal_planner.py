"""Pure logic for meal planning — no I/O, no API calls."""

import random
import re
from datetime import date, timedelta

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Abbreviation lookup: first 3 chars -> index
_DAY_ABBREVS = {name[:3].lower(): i for i, name in enumerate(DAY_NAMES)}


def day_name_to_index(name: str) -> int | None:
    """Convert day name or abbreviation to index (0=Monday). Case-insensitive."""
    key = name.strip().lower()[:3]
    return _DAY_ABBREVS.get(key)


def filter_recipes(objects: list[dict]) -> list[dict]:
    """Keep only objects with type.key == 'recipe'."""
    return [o for o in objects if o.get("type", {}).get("key") == "recipe"]


def filter_meal_plans(objects: list[dict]) -> list[dict]:
    """Keep only objects with type.key == 'meal_plan'."""
    return [o for o in objects if o.get("type", {}).get("key") == "meal_plan"]


def pick_weekly_plan(recipes: list[dict], exclude_names: list[str] | None = None, days: int = 7) -> list[dict]:
    """Pick `days` random recipes, avoiding exclude_names. Allows repeats if needed."""
    exclude = {n.lower() for n in (exclude_names or [])}
    available = [r for r in recipes if r.get("name", "").lower() not in exclude]
    if not available:
        available = list(recipes)
    if not available:
        return []
    if len(available) >= days:
        return random.sample(available, days)
    # Not enough unique recipes — fill with repeats
    plan = list(available)
    while len(plan) < days:
        plan.append(random.choice(available))
    random.shuffle(plan)
    return plan


def swap_day(plan: list[dict], day_index: int, recipes: list[dict], exclude_names: list[str] | None = None) -> list[dict]:
    """Replace one day's recipe in the plan. Returns a new list."""
    if day_index < 0 or day_index >= len(plan):
        raise ValueError(f"Invalid day index: {day_index}")
    exclude = {n.lower() for n in (exclude_names or [])}
    # Also exclude current plan entries to avoid duplicates
    plan_names = {r.get("name", "").lower() for r in plan}
    available = [r for r in recipes if r.get("name", "").lower() not in exclude and r.get("name", "").lower() not in plan_names]
    if not available:
        available = [r for r in recipes if r.get("name", "").lower() not in exclude]
    if not available:
        available = list(recipes)
    new_plan = list(plan)
    new_plan[day_index] = random.choice(available)
    return new_plan


def parse_ingredients(markdown: str) -> list[str]:
    """Extract ingredient lines from markdown (under ## Ingredients)."""
    lines = markdown.split("\n")
    in_section = False
    ingredients = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+Ingredients", stripped, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if re.match(r"^##\s+", stripped):
                break
            if stripped.startswith("- "):
                ingredients.append(stripped[2:].strip())
    return ingredients


def aggregate_shopping_list(recipes: list[dict]) -> list[str]:
    """Flatten + dedup + sort ingredients from multiple recipes."""
    seen = set()
    ingredients = []
    for recipe in recipes:
        body = recipe.get("markdown", "") or recipe.get("body", "")
        for item in parse_ingredients(body):
            key = item.lower()
            if key not in seen:
                seen.add(key)
                ingredients.append(item)
    ingredients.sort(key=str.lower)
    return ingredients


def build_recipe_body(name: str, ingredients: list[str], instructions: list[str]) -> str:
    """Build standard markdown body for a recipe."""
    parts = ["## Ingredients"]
    for ing in ingredients:
        parts.append(f"- {ing}")
    parts.append("")
    parts.append("## Instructions")
    for i, step in enumerate(instructions, 1):
        parts.append(f"{i}. {step}")
    return "\n".join(parts) + "\n"


def parse_plan_body(body: str) -> list[str]:
    """Parse 'Monday: Recipe Name\\n...' -> list of recipe names."""
    names = []
    for line in body.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Match "Monday 2/17: Recipe" or "Monday: Recipe"
        match = re.match(r"^\w+(?:\s+\d+/\d+)?:\s*(.+)$", line)
        if match:
            names.append(match.group(1).strip())
    return names


def build_plan_body(plan: list[dict], start_date: str) -> str:
    """Build 'Monday 2/17: Recipe Name\\n...' from plan list and start date (YYYY-MM-DD)."""
    d = date.fromisoformat(start_date)
    lines = []
    for i, recipe in enumerate(plan):
        day_date = d + timedelta(days=i)
        day_label = f"{DAY_NAMES[i]} {day_date.month}/{day_date.day}"
        lines.append(f"{day_label}: {recipe.get('name', 'Unknown')}")
    return "\n".join(lines) + "\n"


def format_plan_message(plan: list[dict], start_date: str) -> str:
    """Human-readable Telegram message for a weekly plan."""
    d = date.fromisoformat(start_date)
    lines = [f"Meal plan for week of {start_date}:", ""]
    for i, recipe in enumerate(plan):
        day_date = d + timedelta(days=i)
        day_label = f"{DAY_NAMES[i]} {day_date.month}/{day_date.day}"
        lines.append(f"  {day_label}: {recipe.get('name', 'Unknown')}")
    return "\n".join(lines)


def format_shopping_list_message(ingredients: list[str]) -> str:
    """Checkbox-prefixed ingredient list for Telegram."""
    lines = ["Shopping list:", ""]
    for item in ingredients:
        lines.append(f"[ ] {item}")
    return "\n".join(lines)


def format_recipe_message(recipe: dict) -> str:
    """Format a single recipe for Telegram. Truncated to 4000 chars."""
    name = recipe.get("name", "Untitled")
    desc = recipe.get("snippet", "") or recipe.get("description", "")
    body = recipe.get("markdown", "") or recipe.get("body", "")
    parts = [f"*{name}*"]
    if desc:
        parts.append(desc)
    if body:
        parts.append("")
        parts.append(body)
    msg = "\n".join(parts)
    if len(msg) > 4000:
        msg = msg[:3997] + "..."
    return msg


def format_recipes_list_message(recipes: list[dict]) -> str:
    """Numbered list of recipe names."""
    if not recipes:
        return "No recipes found."
    lines = ["Recipes:", ""]
    for i, r in enumerate(recipes, 1):
        lines.append(f"{i}. {r.get('name', 'Untitled')}")
    return "\n".join(lines)


def todays_meal(plan: list[dict], today_weekday: int) -> dict | None:
    """Return recipe for today (0=Monday), or None if out of range."""
    if 0 <= today_weekday < len(plan):
        return plan[today_weekday]
    return None


def current_week_monday() -> date:
    """Return the Monday of the current week."""
    today = date.today()
    return today - timedelta(days=today.weekday())


def current_week_plan_name() -> str:
    """'Week of YYYY-MM-DD' for this week's Monday."""
    return f"Week of {current_week_monday().isoformat()}"
