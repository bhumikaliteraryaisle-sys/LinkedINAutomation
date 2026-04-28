import logging
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from config.settings import settings
from telegram.handlers import (
    handle_topic_selection,
    handle_start,
    handle_manual_topics,
    build_conversation_handler,
)

logger = logging.getLogger(__name__)

_application: Application | None = None


def build_application() -> Application:
    """Build and configure the Telegram Application (singleton)."""
    global _application
    if _application is not None:
        return _application

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Conversation handler (amend + more flows) — must be registered first
    app.add_handler(build_conversation_handler())

    # Topic selection callback
    app.add_handler(CallbackQueryHandler(handle_topic_selection, pattern=r"^topic:.+"))

    # Commands
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("topics", handle_manual_topics))

    _application = app
    return app


async def get_application() -> Application:
    """Async-safe getter for the Application instance."""
    app = build_application()
    if not app.running:
        await app.initialize()
    return app
