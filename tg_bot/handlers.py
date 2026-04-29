import asyncio
import logging
import threading
from telegram import Update, Bot
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
from telegram.constants import ParseMode

from tg_bot.keyboard import posts_message, topic_keyboard
from tg_bot.states import AWAITING_AMEND_INSTRUCTIONS, AWAITING_MORE_INSTRUCTIONS
from tg_bot import state_store
from config.settings import settings

logger = logging.getLogger(__name__)


def _uid(update: Update) -> int:
    return update.effective_user.id


def _only_approved(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == settings.TELEGRAM_APPROVED_USER_ID


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _bg_generate_and_send(topic: str, chat_id: int, message_id: int, user_id: int):
    """Background thread: calls Gemini, edits the Telegram message with results."""
    try:
        from agent.gemini_client import generate_posts
        posts = generate_posts(topic)
        state_store.set(user_id, {"current_topic": topic, "current_posts": posts})
        text, keyboard = posts_message(posts, topic)

        async def send():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        _run_async(send())
    except Exception as e:
        logger.exception("Background generation failed: %s", e)
        async def send_error():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"Sorry, generation failed: {e}\n\nTry /topics again.",
            )
        _run_async(send_error())


def _bg_amend_and_send(original: str, instructions: str, topic: str,
                       post_index: int, chat_id: int, user_id: int):
    """Background thread: amends a post and sends result."""
    try:
        from agent.gemini_client import amend_post
        from tg_bot.keyboard import post_actions_keyboard
        revised = amend_post(original, instructions)
        posts = state_store.get(user_id).get("current_posts", [])
        posts[post_index] = revised
        state_store.update(user_id, current_posts=posts)
        keyboard = post_actions_keyboard(post_index, topic)

        async def send():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=chat_id,
                text=f"*Revised Post {post_index + 1}:*\n\n{revised}",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        _run_async(send())
    except Exception as e:
        logger.exception("Background amend failed: %s", e)


def _bg_more_and_send(topic: str, direction: str, chat_id: int, user_id: int):
    """Background thread: generates more posts and sends result."""
    try:
        from agent.gemini_client import more_posts
        posts = more_posts(topic, direction)
        state_store.update(user_id, current_posts=posts, current_topic=topic)
        text, keyboard = posts_message(posts, topic)

        async def send():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        _run_async(send())
    except Exception as e:
        logger.exception("Background more_posts failed: %s", e)


# ── topic selection ───────────────────────────────────────────────────────────

async def handle_topic_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _only_approved(update):
        return

    topic = query.data.removeprefix("topic:")
    msg = await query.edit_message_text(
        f"Generating 3 posts for *{topic}*\n\nPlease wait ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Fire background thread — returns 200 to Telegram immediately
    t = threading.Thread(
        target=_bg_generate_and_send,
        args=(topic, msg.chat_id, msg.message_id, _uid(update)),
        daemon=True,
    )
    t.start()


# ── amend flow ────────────────────────────────────────────────────────────────

async def handle_amend_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()
    if not _only_approved(update):
        return ConversationHandler.END

    _, post_index_str, topic_slug = query.data.split(":", 2)
    state_store.update(_uid(update), amend_post_index=int(post_index_str), amend_topic=topic_slug)

    post_num = int(post_index_str) + 1
    await query.message.reply_text(
        f"What changes for *Post {post_num}*?\n\n"
        "e.g. _Make it shorter_ / _Add an example_ / _More casual_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AWAITING_AMEND_INSTRUCTIONS


async def handle_amend_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _only_approved(update):
        return ConversationHandler.END

    instructions = update.message.text.strip()
    state = state_store.get(_uid(update))
    post_index = state.get("amend_post_index", 0)
    topic = state.get("amend_topic", state.get("current_topic", ""))
    posts = state.get("current_posts", [])

    if post_index >= len(posts):
        await update.message.reply_text("Couldn't find the original post. Use /topics to start again.")
        return ConversationHandler.END

    await update.message.reply_text("Revising... ⏳")

    t = threading.Thread(
        target=_bg_amend_and_send,
        args=(posts[post_index], instructions, topic, post_index,
              update.effective_chat.id, _uid(update)),
        daemon=True,
    )
    t.start()
    return ConversationHandler.END


# ── more flow ─────────────────────────────────────────────────────────────────

async def handle_more_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()
    if not _only_approved(update):
        return ConversationHandler.END

    _, post_index_str, topic_slug = query.data.split(":", 2)
    state_store.update(_uid(update), more_topic=topic_slug)

    await query.message.reply_text(
        f"Any direction for more posts on *{topic_slug}*?\n\n"
        "e.g. _more data-driven_ / _story format_ — or /skip",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AWAITING_MORE_INSTRUCTIONS


async def handle_more_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _only_approved(update):
        return ConversationHandler.END

    direction = update.message.text.strip()
    if direction == "/skip":
        direction = ""

    state = state_store.get(_uid(update))
    topic = state.get("more_topic", state.get("current_topic", ""))

    await update.message.reply_text("Generating fresh posts... ⏳")

    t = threading.Thread(
        target=_bg_more_and_send,
        args=(topic, direction, update.effective_chat.id, _uid(update)),
        daemon=True,
    )
    t.start()
    return ConversationHandler.END


async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await handle_more_instructions(update, context)


# ── commands ──────────────────────────────────────────────────────────────────

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _only_approved(update):
        return
    await update.message.reply_text(
        "Hi! I'm your LinkedIn content assistant.\n\n"
        "Every morning at 9AM IST I'll send you 5 trending topics.\n"
        "Or use /topics to get them right now."
    )


async def handle_manual_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _only_approved(update):
        return

    await update.message.reply_text("Fetching trending topics... ⏳")

    from agent.scrapers import fetch_all_trends
    from agent.topic_ranker import get_top_5_topics
    trends = fetch_all_trends()
    topics = get_top_5_topics(trends)
    keyboard = topic_keyboard(topics)
    await update.message.reply_text("Choose a topic for your LinkedIn post:", reply_markup=keyboard)


# ── conversation handler ──────────────────────────────────────────────────────

def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_amend_start, pattern=r"^amend:\d+:.+"),
            CallbackQueryHandler(handle_more_start, pattern=r"^more:\d+:.+"),
        ],
        states={
            AWAITING_AMEND_INSTRUCTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amend_instructions),
            ],
            AWAITING_MORE_INSTRUCTIONS: [
                CommandHandler("skip", handle_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_more_instructions),
            ],
        },
        fallbacks=[],
        per_message=False,
    )
