import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
from telegram.constants import ParseMode

from agent.gemini_client import generate_posts, amend_post, more_posts
from tg_bot.keyboard import posts_message, topic_keyboard
from tg_bot.states import AWAITING_AMEND_INSTRUCTIONS, AWAITING_MORE_INSTRUCTIONS
from tg_bot import state_store
from config.settings import settings

logger = logging.getLogger(__name__)


def _uid(update: Update) -> int:
    return update.effective_user.id


def _only_approved(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == settings.TELEGRAM_APPROVED_USER_ID


# ── topic selection ───────────────────────────────────────────────────────────

async def handle_topic_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _only_approved(update):
        return

    topic = query.data.removeprefix("topic:")
    await query.edit_message_text(
        f"Generating 3 posts for:\n*{topic}*\n\nPlease wait...",
        parse_mode=ParseMode.MARKDOWN,
    )

    posts = generate_posts(topic)
    state_store.set(_uid(update), {"current_topic": topic, "current_posts": posts})

    text, keyboard = posts_message(posts, topic)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


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
        f"What changes do you want for *Post {post_num}*?\n\n"
        "Examples:\n• _Make it shorter_\n• _Add a concrete example_\n• _Make it more casual_",
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
        await update.message.reply_text("Couldn't find the original post. Please select a topic again.")
        return ConversationHandler.END

    await update.message.reply_text("Revising post...")
    revised = amend_post(posts[post_index], instructions)
    posts[post_index] = revised
    state_store.update(_uid(update), current_posts=posts)

    from tg_bot.keyboard import post_actions_keyboard
    keyboard = post_actions_keyboard(post_index, topic)
    await update.message.reply_text(
        f"*Revised Post {post_index + 1}:*\n\n{revised}",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )
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
        f"Generating 3 more posts on *{topic_slug}*.\n\n"
        "Any direction? (e.g. _more data-driven_, _story format_, _contrarian take_)\n"
        "Or send /skip for fresh variants without guidance.",
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

    await update.message.reply_text("Generating fresh posts...")
    posts = more_posts(topic, direction)
    state_store.update(_uid(update), current_posts=posts, current_topic=topic)

    text, keyboard = posts_message(posts, topic)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END


async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await handle_more_instructions(update, context)


# ── commands ──────────────────────────────────────────────────────────────────

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _only_approved(update):
        return
    await update.message.reply_text(
        "Hi! I'm your LinkedIn content assistant.\n\n"
        "Every morning at 9AM IST I'll send you 5 trending topics to pick from.\n"
        "You can also use /topics to get topics right now."
    )


async def handle_manual_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _only_approved(update):
        return
    await update.message.reply_text("Fetching trending topics...")

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
