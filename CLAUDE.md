# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

anytype-apps is a collection of life management tools built on top of Anytype's HTTP API. It includes a Python export/backup script and documentation for setting up shared Anytype spaces (starting with meal prep).

## Running

```bash
# Install dependencies
pip install requests python-dotenv

# Run the export/backup script
python export.py
```

## Dependencies

- Python 3.10+ (uses `X | Y` union syntax)
- `requests` library (HTTP API calls)
- `python-dotenv` library (env file loading)
- Anytype CLI (`anytype serve` must be running)

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
