#!/usr/bin/env python3
"""Set up meal prep types, properties, and sample objects in the test space."""

import anytype_api

SPACE_ID = "bafyreicqqydmxrx4a2huxxcxome4vq3ovn3lgdxvdy7ktiyp5xh5ld4bxq.1tgkqb3hjg356"

PROPERTIES = [
    ("Prep Time", "prep_time", "number"),
    ("Cook Time", "cook_time", "number"),
    ("Servings", "servings", "number"),
    ("Ingredients", "ingredients", "text"),
    ("Instructions", "instructions", "text"),
    ("Meal Type", "meal_type", "select"),
    ("Date", "meal_date", "date"),
    ("Recipes", "recipes", "objects"),
]

SAMPLE_RECIPES = [
    {
        "name": "Overnight Oats",
        "body": (
            "## Ingredients\n"
            "- 1/2 cup rolled oats\n"
            "- 1/2 cup milk\n"
            "- 1/4 cup yogurt\n"
            "- 1 tbsp chia seeds\n"
            "- 1 tbsp honey\n"
            "- Fresh fruit for topping\n\n"
            "## Instructions\n"
            "1. Mix oats, milk, yogurt, chia seeds, and honey in a jar\n"
            "2. Refrigerate overnight (or at least 4 hours)\n"
            "3. Top with fresh fruit before serving\n"
        ),
        "description": "Quick no-cook breakfast, 5 min prep",
    },
    {
        "name": "Chicken Stir-Fry",
        "body": (
            "## Ingredients\n"
            "- 500g chicken breast, sliced\n"
            "- 2 cups mixed vegetables (bell peppers, broccoli, carrots)\n"
            "- 3 tbsp soy sauce\n"
            "- 1 tbsp sesame oil\n"
            "- 2 cloves garlic, minced\n"
            "- 1 tbsp ginger, grated\n"
            "- Rice for serving\n\n"
            "## Instructions\n"
            "1. Cook rice according to package directions\n"
            "2. Heat sesame oil in a wok over high heat\n"
            "3. Cook chicken until golden, about 5 minutes\n"
            "4. Add garlic, ginger, and vegetables, stir-fry 3-4 minutes\n"
            "5. Add soy sauce, toss to combine\n"
            "6. Serve over rice\n"
        ),
        "description": "20 min weeknight dinner, serves 4",
    },
    {
        "name": "Mediterranean Pasta Salad",
        "body": (
            "## Ingredients\n"
            "- 400g pasta (fusilli or penne)\n"
            "- 200g cherry tomatoes, halved\n"
            "- 1 cucumber, diced\n"
            "- 150g feta cheese, crumbled\n"
            "- 100g kalamata olives\n"
            "- 1/4 red onion, thinly sliced\n"
            "- 3 tbsp olive oil\n"
            "- 2 tbsp red wine vinegar\n"
            "- Salt, pepper, oregano to taste\n\n"
            "## Instructions\n"
            "1. Cook pasta, drain and cool\n"
            "2. Combine all vegetables in a large bowl\n"
            "3. Add cooled pasta\n"
            "4. Whisk olive oil, vinegar, and seasonings\n"
            "5. Toss everything together\n"
            "6. Refrigerate 30 min before serving (tastes better cold)\n"
        ),
        "description": "Great for meal prep, keeps 3-4 days in fridge",
    },
]


def create_properties():
    print("Creating properties...")
    for name, key, fmt in PROPERTIES:
        try:
            prop = anytype_api.create_property(SPACE_ID, name, key, fmt)
            p = prop.get("property", {})
            print(f"  {p.get('name')}: {p.get('format')} ({p.get('id', '')[:20]}...)")
        except Exception as e:
            print(f"  Warning: {name}: {e}")


def create_sample_recipes():
    print("\nCreating sample recipes...")
    for recipe in SAMPLE_RECIPES:
        try:
            result = anytype_api.create_object(
                SPACE_ID,
                type_key="recipe",
                name=recipe["name"],
                body=recipe["body"],
                description=recipe["description"],
                icon={"format": "emoji", "emoji": "🍳"},
            )
            obj = result.get("object", {})
            print(f"  Created: {obj.get('name')} ({obj.get('id', '')[:20]}...)")
        except Exception as e:
            print(f"  Warning: {recipe['name']}: {e}")


def main():
    create_properties()
    create_sample_recipes()
    print("\nDone! Check your Anytype app to see the new types and recipes.")


if __name__ == "__main__":
    main()
