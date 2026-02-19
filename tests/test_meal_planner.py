"""Tests for meal_planner.py — pure logic, no I/O."""

import pytest

from meal_planner import (
    DAY_NAMES,
    aggregate_shopping_list,
    build_plan_body,
    build_recipe_body,
    current_week_plan_name,
    day_name_to_index,
    filter_meal_plans,
    filter_recipes,
    format_plan_message,
    format_recipe_message,
    format_recipes_list_message,
    format_shopping_list_message,
    parse_ingredients,
    parse_plan_body,
    pick_weekly_plan,
    swap_day,
    todays_meal,
)


def _recipe(name: str, body: str = "", description: str = "") -> dict:
    """Minimal recipe object matching Anytype shape."""
    return {
        "object": "object",
        "id": f"fake-id-{name.lower().replace(' ', '-')}",
        "name": name,
        "type": {"object": "type", "key": "recipe", "name": "Recipe"},
        "snippet": description,
        "markdown": body,
    }


def _meal_plan(name: str, body: str = "") -> dict:
    return {
        "object": "object",
        "id": f"fake-id-{name.lower().replace(' ', '-')}",
        "name": name,
        "type": {"object": "type", "key": "meal_plan", "name": "Meal Plan"},
        "markdown": body,
    }


STIR_FRY_BODY = (
    "## Ingredients\n"
    "- 500g chicken breast, sliced\n"
    "- 2 cups mixed vegetables\n"
    "- 3 tbsp soy sauce\n\n"
    "## Instructions\n"
    "1. Cook rice\n"
    "2. Stir-fry chicken\n"
    "3. Add vegetables and sauce\n"
)

PASTA_BODY = (
    "## Ingredients\n"
    "- 400g pasta\n"
    "- 200g cherry tomatoes\n"
    "- 3 tbsp soy sauce\n\n"
    "## Instructions\n"
    "1. Cook pasta\n"
    "2. Combine everything\n"
)

RECIPES = [
    _recipe("Chicken Stir-Fry", STIR_FRY_BODY, "Quick weeknight dinner"),
    _recipe("Mediterranean Pasta Salad", PASTA_BODY, "Great for meal prep"),
    _recipe("Overnight Oats", "## Ingredients\n- Oats\n- Milk\n"),
]


# --- day_name_to_index ---

class TestDayNameToIndex:
    def test_full_names(self):
        for i, name in enumerate(DAY_NAMES):
            assert day_name_to_index(name) == i

    def test_case_insensitive(self):
        assert day_name_to_index("monday") == 0
        assert day_name_to_index("FRIDAY") == 4

    def test_abbreviations(self):
        assert day_name_to_index("Mon") == 0
        assert day_name_to_index("fri") == 4
        assert day_name_to_index("Sun") == 6

    def test_garbage(self):
        assert day_name_to_index("xyz") is None
        assert day_name_to_index("") is None


# --- filter_recipes / filter_meal_plans ---

class TestFilters:
    def test_filter_recipes(self):
        mixed = RECIPES + [_meal_plan("Week of 2026-02-16")]
        result = filter_recipes(mixed)
        assert len(result) == 3
        assert all(r["type"]["key"] == "recipe" for r in result)

    def test_filter_meal_plans(self):
        mixed = RECIPES + [_meal_plan("Week of 2026-02-16")]
        result = filter_meal_plans(mixed)
        assert len(result) == 1
        assert result[0]["name"] == "Week of 2026-02-16"

    def test_filter_empty(self):
        assert filter_recipes([]) == []
        assert filter_meal_plans([]) == []


# --- pick_weekly_plan ---

class TestPickWeeklyPlan:
    def test_no_repeats_with_enough_recipes(self):
        recipes = [_recipe(f"Recipe {i}") for i in range(10)]
        plan = pick_weekly_plan(recipes)
        assert len(plan) == 7
        names = [r["name"] for r in plan]
        assert len(set(names)) == 7  # all unique

    def test_allows_repeats_with_few_recipes(self):
        recipes = [_recipe("A"), _recipe("B")]
        plan = pick_weekly_plan(recipes)
        assert len(plan) == 7

    def test_respects_exclusions(self):
        recipes = [_recipe("A"), _recipe("B"), _recipe("C")]
        plan = pick_weekly_plan(recipes, exclude_names=["A"], days=2)
        names = [r["name"] for r in plan]
        assert "A" not in names

    def test_empty_recipes(self):
        assert pick_weekly_plan([]) == []

    def test_all_excluded_falls_back(self):
        recipes = [_recipe("A")]
        plan = pick_weekly_plan(recipes, exclude_names=["A"], days=1)
        assert len(plan) == 1  # falls back to full list


# --- swap_day ---

class TestSwapDay:
    def test_swaps_correctly(self):
        plan = [_recipe("A"), _recipe("B"), _recipe("C")]
        recipes = [_recipe("D"), _recipe("E")]
        new_plan = swap_day(plan, 1, recipes)
        assert new_plan[0]["name"] == "A"
        assert new_plan[1]["name"] in ("D", "E")
        assert new_plan[2]["name"] == "C"
        assert len(new_plan) == 3

    def test_bad_index(self):
        with pytest.raises(ValueError):
            swap_day([_recipe("A")], 5, [_recipe("B")])
        with pytest.raises(ValueError):
            swap_day([_recipe("A")], -1, [_recipe("B")])

    def test_original_unchanged(self):
        plan = [_recipe("A"), _recipe("B")]
        recipes = [_recipe("C")]
        new_plan = swap_day(plan, 0, recipes)
        assert plan[0]["name"] == "A"  # original unchanged
        assert new_plan[0]["name"] == "C"


# --- parse_ingredients ---

class TestParseIngredients:
    def test_real_markdown(self):
        result = parse_ingredients(STIR_FRY_BODY)
        assert result == [
            "500g chicken breast, sliced",
            "2 cups mixed vegetables",
            "3 tbsp soy sauce",
        ]

    def test_empty_body(self):
        assert parse_ingredients("") == []

    def test_no_ingredients_section(self):
        assert parse_ingredients("## Instructions\n1. Do stuff\n") == []

    def test_anytype_trailing_spaces(self):
        """Anytype markdown has trailing spaces on lines."""
        body = "## Ingredients   \n- Oats   \n- Milk   \n## Instructions   \n"
        result = parse_ingredients(body)
        assert result == ["Oats", "Milk"]


# --- aggregate_shopping_list ---

class TestAggregateShoppingList:
    def test_dedup_and_sort(self):
        r1 = _recipe("A", STIR_FRY_BODY)
        r2 = _recipe("B", PASTA_BODY)
        result = aggregate_shopping_list([r1, r2])
        assert "3 tbsp soy sauce" in result  # deduped
        assert result.count("3 tbsp soy sauce") == 1
        assert result == sorted(result, key=str.lower)

    def test_empty(self):
        assert aggregate_shopping_list([]) == []


# --- build_recipe_body round-trip ---

class TestBuildRecipeBody:
    def test_round_trip(self):
        ingredients = ["Oats", "Milk", "Honey"]
        instructions = ["Mix everything", "Refrigerate overnight"]
        body = build_recipe_body("Test", ingredients, instructions)
        parsed = parse_ingredients(body)
        assert parsed == ingredients
        assert "1. Mix everything" in body
        assert "2. Refrigerate overnight" in body


# --- parse_plan_body / build_plan_body round-trip ---

class TestPlanBody:
    def test_parse_simple(self):
        body = "Monday: Oats\nTuesday: Pasta\nWednesday: Stir-Fry\n"
        names = parse_plan_body(body)
        assert names == ["Oats", "Pasta", "Stir-Fry"]

    def test_parse_with_dates(self):
        body = "Monday 2/17: Oats\nTuesday 2/18: Pasta\n"
        names = parse_plan_body(body)
        assert names == ["Oats", "Pasta"]

    def test_build_plan_body(self):
        plan = [_recipe("Oats"), _recipe("Pasta")]
        body = build_plan_body(plan, "2026-02-16")
        assert "Monday 2/16: Oats" in body
        assert "Tuesday 2/17: Pasta" in body

    def test_round_trip(self):
        plan = [_recipe(f"Recipe {i}") for i in range(7)]
        body = build_plan_body(plan, "2026-02-16")
        names = parse_plan_body(body)
        assert names == [f"Recipe {i}" for i in range(7)]


# --- format functions ---

class TestFormatting:
    def test_format_plan_message(self):
        plan = [_recipe("Oats"), _recipe("Pasta")]
        msg = format_plan_message(plan, "2026-02-16")
        assert "Meal plan for week of 2026-02-16" in msg
        assert "Monday 2/16: Oats" in msg

    def test_format_shopping_list(self):
        msg = format_shopping_list_message(["Oats", "Milk"])
        assert "[ ] Oats" in msg
        assert "[ ] Milk" in msg

    def test_format_recipe_message(self):
        msg = format_recipe_message(RECIPES[0])
        assert "*Chicken Stir-Fry*" in msg
        assert "Quick weeknight dinner" in msg

    def test_format_recipe_truncation(self):
        recipe = _recipe("Big", "x" * 5000)
        msg = format_recipe_message(recipe)
        assert len(msg) <= 4000
        assert msg.endswith("...")

    def test_format_recipes_list(self):
        msg = format_recipes_list_message(RECIPES)
        assert "1. Chicken Stir-Fry" in msg
        assert "3. Overnight Oats" in msg

    def test_format_recipes_list_empty(self):
        assert format_recipes_list_message([]) == "No recipes found."


# --- todays_meal ---

class TestTodaysMeal:
    def test_valid_day(self):
        plan = [_recipe(f"R{i}") for i in range(7)]
        assert todays_meal(plan, 0)["name"] == "R0"
        assert todays_meal(plan, 6)["name"] == "R6"

    def test_out_of_range(self):
        assert todays_meal([], 0) is None
        assert todays_meal([_recipe("A")], 7) is None


# --- current_week_plan_name ---

class TestCurrentWeekPlanName:
    def test_format(self):
        name = current_week_plan_name()
        assert name.startswith("Week of ")
        # Should be a valid date
        date_str = name.replace("Week of ", "")
        from datetime import date
        d = date.fromisoformat(date_str)
        assert d.weekday() == 0  # Monday
