# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

anytype-apps is a collection of life management tools built on top of Anytype's HTTP API. It includes a bidirectional backup system (export + restore), setup scripts for shared Anytype spaces, and a Claude-powered Telegram bot for meal planning. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.

## Running

```bash
# Export all spaces to git (auto-commits)
./export.py

# Restore from git back into Anytype
./restore.py

# Set up meal prep types and sample recipes
./setup_meal_prep.py

# Run the Telegram bot
python bot.py
```

All scripts require `anytype serve` to be running (or the systemd service).

## Dependencies

- Python 3.10+ (uses `X | Y` union syntax)
- `requests` and `python-dotenv` (installed system-wide via apt)
- `python-telegram-bot` — async Telegram bot framework
- `anthropic` — Claude API client for AI-powered free-text handling
- Anytype CLI installed at `~/.local/bin/anytype`

## Anytype API Key Learnings

- **Local HTTP API** runs at `http://127.0.0.1:31012` when `anytype serve` is running.
- **API version header** is required: `Anytype-Version: 2025-05-21`.
- **Rate limiting**: burst of 60, sustained 1 req/sec. All calls in `anytype_api.py` enforce this.
- **GET `/v1/spaces/{id}/objects/{id}`** returns a `markdown` field with the full body content. This is more reliable than the `/export/markdown` endpoint, which returns 404 for objects in shared spaces.
- **PATCH `/v1/spaces/{id}/objects/{id}`** works for updating `name`, `description`, and `body` (markdown).
- **POST `/v1/spaces/{id}/objects`** requires `type_key` (not type ID) and `name`. Optional: `body`, `description`, `icon`.
- **POST `/v1/spaces/{id}/types`** requires `name`, `key`, and `plural_name`.
- **POST `/v1/spaces/{id}/properties`** requires `name`, `key`, and `format`.
- **Search** (`POST /v1/spaces/{id}/search`) with empty query returns all objects. Paginate with `limit` and `offset`.
- **Bot accounts** are separate from user accounts. Created via `anytype auth create <name>`. The bot must be invited to a user's space and approved as a member.
- The bot's account key is the only way to re-authenticate — store it securely.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design including the Telegram bot and Claude integration.

```
anytype_api.py       # Thin HTTP API wrapper (get, post, patch, delete + rate limiting)
export.py            # Export all spaces → export/<space>/<type>/<name>.{json,md}, auto-commits
restore.py           # Restore from export/ → Anytype (update existing, recreate missing)
setup_meal_prep.py   # One-time setup: creates Recipe/Meal Plan/Shopping List types + sample data
bot.py               # Telegram bot entry point
bot_handlers.py      # Command handlers (/plan_week, /recipes, etc.)
bot_ai.py            # Claude API integration — system prompt, tool defs, message loop
meal_planner.py      # Pure logic — random plan generation, ingredient aggregation, dedup
.env                 # API keys, bot token, allowed users (gitignored)
export/              # Exported data, committed to git
  <space>/
    _types.json      # All type definitions in the space
    _properties.json # All property definitions in the space
    <type_key>/
      <name>.json    # Full object metadata from GET /objects/:id
      <name>.md      # Markdown body content
```

## Coding Style

- **No OOP patterns.** Do not use inheritance, polymorphism, or class hierarchies. Dataclasses for holding data are fine; classes with methods that dispatch on type or override behavior are not. Think C/Rust, not Java.
- **Small, focused functions.** Aim for 5-10 lines per function. Extract logic into named helpers rather than writing long functions.
- **Pure functions where possible.** Functions should take inputs, return outputs, and avoid side effects. Side effects (I/O, mutating shared state) should be pushed to the edges — thin handler functions that call pure logic.
- **Test everything with pytest.** Every non-trivial function should have corresponding tests in `tests/`. Pure functions are easy to test; if a function is hard to test, it probably does too much.

## Git Workflow

- **Always commit and push when you're done with a task.** Do not wait to be asked — committing and pushing is part of completing the work.
- Create small, focused commits as you go so changes are easy to review and revert.
- Each commit should address a single concern (one bug fix, one feature, one refactor).
- Use a succinct imperative commit title (e.g. "Add retry logic for API calls").
- Include gotchas, caveats, or non-obvious side effects in the commit message body.
- Never add "Co-Authored-By" lines or email addresses to commit messages.
- Push freely without asking, but never use `git push --force` or any force-push variant.
- **Keep all documentation up to date.** When changing behavior, update CLAUDE.md and code comments in the same commit. Stale docs are worse than no docs.

## Configuration

Copy `.env.example` to `.env` and fill in your values:

- `ANYTYPE_API_URL` — local API endpoint (default `http://127.0.0.1:31012`)
- `ANYTYPE_API_KEY` — API key from `anytype auth apikey create`
- `TELEGRAM_BOT_TOKEN` — from @BotFather on Telegram
- `TELEGRAM_ALLOWED_USERS` — comma-separated Telegram user IDs
- `ANTHROPIC_API_KEY` — Claude API key for AI-powered free-text handling

## Bot Commands

- `/recipes` — list all recipes
- `/plan_week [exclude...]` — generate a random 7-day meal plan (optionally excluding recipes)
- `/whats_for_dinner` — show today's planned meal
- `/shopping_list` — aggregated ingredients from this week's plan
- `/add_recipe Name` — create an empty recipe in Anytype
- `/swap <day> [exclude...]` — replace one day's meal
- Free text messages are handled by Claude AI (tool-use agent loop with `MAX_TOOL_ROUNDS=5`)

## Current Spaces

- **test** — shared space with meal prep data (Recipe, Meal Plan, Shopping List types)
- **Graceful Cheddar** — bot's personal space (unused)
