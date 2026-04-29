import json
import logging
import asyncio
from http.server import BaseHTTPRequestHandler

from config.settings import settings

logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for GET /api/cron — triggered by Vercel Cron."""

    def do_GET(self):
        # Validate the request is from Vercel Cron or an authorized caller
        secret = self.headers.get("x-cron-secret", "")
        if settings.CRON_SECRET and secret != settings.CRON_SECRET:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error": "unauthorized"}')
            return

        try:
            asyncio.run(self._run_pipeline())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        except Exception as e:
            logger.exception("Cron job error: %s", e)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    async def _run_pipeline(self):
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

    def log_message(self, format, *args):
        pass
