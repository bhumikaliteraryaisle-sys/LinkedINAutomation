import json
import logging
from http.server import BaseHTTPRequestHandler

from telegram import Update

logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for POST /api/webhook"""

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Import here to avoid import-time side effects on cold starts
            import asyncio
            from telegram.bot import get_application

            async def process():
                app = await get_application()
                update = Update.de_json(data, app.bot)
                await app.process_update(update)

            asyncio.run(process())

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        except Exception as e:
            logger.exception("Webhook error: %s", e)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": false}')

    def log_message(self, format, *args):
        pass  # suppress default HTTP logging
