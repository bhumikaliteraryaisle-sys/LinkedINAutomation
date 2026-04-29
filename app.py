import asyncio
import json
import logging
import os

from flask import Flask, request, jsonify

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine from a sync Flask route."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    return asyncio.run(coro)


# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "LinkedIn Agent is running"})


@app.route("/api/webhook", methods=["POST"])
def webhook():
    """Receives Telegram updates via webhook."""
    try:
        from telegram import Update
        from tg_bot.bot import get_application

        data = request.get_json(force=True)

        async def process():
            tg_app = await get_application()
            update = Update.de_json(data, tg_app.bot)
            await tg_app.process_update(update)

        _run(process())
        return jsonify({"ok": True})
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cron", methods=["GET"])
def cron():
    """Triggered by Vercel Cron at 9AM IST — sends 5 topic buttons to Telegram."""
    from config.settings import settings

    # Validate cron secret to prevent unauthorized triggers
    secret = request.headers.get("x-cron-secret", "")
    if settings.CRON_SECRET and secret != settings.CRON_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    try:
        async def run_pipeline():
            from agent.scrapers import fetch_all_trends
            from agent.topic_ranker import get_top_5_topics
            from tg_bot.keyboard import topic_keyboard
            from telegram import Bot

            trends = fetch_all_trends()
            topics = get_top_5_topics(trends)
            logger.info("Daily topics: %s", topics)

            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            keyboard = topic_keyboard(topics)
            await bot.send_message(
                chat_id=settings.TELEGRAM_APPROVED_USER_ID,
                text="Good morning! Choose today's LinkedIn post topic:",
                reply_markup=keyboard,
            )
            return topics

        topics = _run(run_pipeline())
        return jsonify({"ok": True, "topics": topics})
    except Exception as e:
        logger.exception("Cron error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
