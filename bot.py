#!/usr/bin/env python3
"""Telegram bot entry point for the meal planning assistant."""

import os

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

import bot_handlers

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USERS = {
    int(uid.strip())
    for uid in os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
    if uid.strip()
}


def check_user(user_id: int) -> bool:
    """Return True if the user is in the allow-list (or list is empty)."""
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def _wrap_auth(handler):
    """Wrap a handler with user authentication."""
    async def wrapper(update, context):
        if not check_user(update.effective_user.id):
            await update.message.reply_text("Unauthorized.")
            return
        return await handler(update, context)
    return wrapper


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    commands = [
        ("plan_week", bot_handlers.plan_week),
        ("whats_for_dinner", bot_handlers.whats_for_dinner),
        ("shopping_list", bot_handlers.shopping_list),
        ("add_recipe", bot_handlers.add_recipe),
        ("recipes", bot_handlers.recipes),
        ("swap", bot_handlers.swap),
    ]
    for name, handler in commands:
        app.add_handler(CommandHandler(name, _wrap_auth(handler)))

    # Free-text handler (Phase 3) — import lazily to avoid hard dep on anthropic
    try:
        from bot_ai import handle_free_text
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            _wrap_auth(handle_free_text),
        ))
    except ImportError:
        pass

    print("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
