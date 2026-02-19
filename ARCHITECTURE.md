# Architecture

## System Overview

```
┌─────────────┐     ┌─────────────┐
│ Anytype app  │     │  Telegram   │
│  (phone)     │     │  (phone)    │
│              │     │             │
│ Data entry   │     │ Commands +  │
│ Browse/edit  │     │ free text   │
└──────┬───────┘     └──────┬──────┘
       │ sync               │ Bot API
       ▼                    ▼
┌─────────────┐     ┌─────────────────┐
│ anytype      │     │ Telegram bot    │
│ serve        │◄───►│ (python)        │
│ (:31012)     │     │                 │
└─────────────┘     │ ┌─────────────┐ │
                    │ │ Claude API  │ │
       ▲            │ │ (reasoning) │ │
       │            │ └─────────────┘ │
       │            └────────┬────────┘
       │                     │
       ▼                     ▼
┌─────────────┐     ┌─────────────┐
│ Git repo     │     │ Anytype API │
│ (backup)     │     │ (read/write)│
└─────────────┘     └─────────────┘
```

## Components

- **Anytype** — source of truth for all data. Humans edit here (phone/desktop). Bot reads and writes here too. Pure data, no logic.
- **anytype_api.py** — existing Python wrapper, reused by the bot.
- **Telegram bot** — the logic/execution front end. Handles commands, free-text prompts, inline buttons for confirmations.
- **Claude API** — powers natural language understanding. The bot sends user messages + context (current recipes, recent plans) to Claude, which decides what to do and returns structured actions.
- **Export/restore** — existing backup scripts, unchanged. Run on cron.

## Bot Capabilities

### Commands

- `/plan_week` — generate randomized 7-day dinner plan, avoiding recent meals
- `/whats_for_dinner` — show today's planned meal
- `/shopping_list` — aggregate ingredients from current week's plan
- `/add_recipe` — quick-add a recipe (name + description)
- `/recipes` — list all recipes
- `/swap <day>` — replace one day's meal with a new random pick

### Free-text (Claude-powered)

- "Find me a quick Thai curry recipe" → Claude searches/creates a recipe, adds to Anytype
- "Plan something light for Friday" → Claude picks an appropriate recipe and updates the plan
- "We have chicken and broccoli, what can we make?" → Claude suggests from existing recipes or creates new ones
- "Add my mom's lasagna recipe" → Claude asks follow-up questions, builds the recipe object
- "What did we eat last week?" → Claude queries recent meal plans and summarizes

## Claude Integration Design

The bot gives Claude a system prompt describing:
- Available tools (list recipes, create recipe, plan week, get meal plan, etc.)
- The current state (this week's plan, recent history)
- User preferences (dietary restrictions, serving size, etc.)

Claude responds with either:
- A direct text reply (conversational)
- Tool calls (structured actions to execute against Anytype)

This is essentially **Claude as an agent with Anytype tools**. We use the Anthropic API's tool_use feature — define tools that map to anytype_api.py functions, let Claude decide when to call them.

### Tool definitions for Claude

```
list_recipes()          → fetch all Recipe objects
get_recipe(name)        → search for a specific recipe
create_recipe(...)      → create a new Recipe in Anytype
plan_week(exclude=[])   → random 7-day plan avoiding listed recipes
get_current_plan()      → this week's meal plan
swap_meal(day, recipe)  → replace one day's meal
get_shopping_list()     → aggregate ingredients from plan
search_web(query)       → web search for recipe ideas (optional)
```

### Data flow: free-text example

1. User sends: "find me something easy with pasta for tonight"
2. Bot builds Claude message with: system prompt + tools + user message + context (today's plan, all recipes)
3. Claude reasons: "I should check existing pasta recipes first, then suggest or create one"
4. Claude calls `list_recipes()` → bot executes against Anytype, returns results
5. Claude sees Mediterranean Pasta Salad exists, suggests it
6. If user confirms → Claude calls `swap_meal("wednesday", "Mediterranean Pasta Salad")`
7. Bot updates Anytype, confirms to user

## Auth

- Telegram bot token in `.env`
- `allowed_users` list (Telegram user IDs) — same pattern as auto-slicer2
- Claude/Anthropic API key in `.env`

## Deployment

- systemd user service (same pattern as auto-slicer2)
- Requires `anytype serve` running alongside
- Two services: `anytype-serve.service` + `meal-bot.service`

## File Structure

```
anytype_api.py          # Existing — Anytype HTTP API wrapper
export.py               # Existing — backup to git
restore.py              # Existing — restore from git
setup_meal_prep.py      # Existing — one-time type/property setup
bot.py                  # Telegram bot entry point
bot_handlers.py         # Command handlers (/plan_week, /recipes, etc.)
bot_ai.py               # Claude API integration — system prompt, tool defs, message loop
meal_planner.py         # Pure logic — random plan generation, ingredient aggregation, dedup
.env                    # Bot token, API keys, allowed users
```
