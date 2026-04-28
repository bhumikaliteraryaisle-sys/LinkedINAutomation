"""
One-time script to register your Telegram bot's webhook with Vercel.

Usage:
  python scripts/register_webhook.py --url https://your-project.vercel.app
"""
import argparse
import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def register(vercel_url: str):
    webhook_url = vercel_url.rstrip("/") + "/api/webhook"
    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook",
        json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]},
    )
    data = resp.json()
    if data.get("ok"):
        print(f"Webhook registered: {webhook_url}")
    else:
        print(f"Failed: {data}")
        sys.exit(1)


def check():
    resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo")
    import json
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Your Vercel deployment URL, e.g. https://my-app.vercel.app")
    parser.add_argument("--check", action="store_true", help="Print current webhook info")
    args = parser.parse_args()

    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    if args.check:
        check()
    elif args.url:
        register(args.url)
    else:
        parser.print_help()
