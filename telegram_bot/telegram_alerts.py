# telegram_alerts.py
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
if not TELEGRAM_CHAT_ID:
    raise RuntimeError("TELEGRAM_CHAT_ID not set in .env")


async def send_telegram_async(text: str, parse_mode: Optional[str] = None) -> None:
    """
    Async version – use if your strategy is already asyncio-based.
    """
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    async with httpx.AsyncClient() as client:
        resp = await client.post(base_url, json=payload, timeout=10.0)
        resp.raise_for_status()


def send_telegram(text: str, parse_mode: Optional[str] = None) -> None:
    """
    Sync version – safe to call from any normal code path.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: just run it
        asyncio.run(send_telegram_async(text, parse_mode=parse_mode))
    else:
        # Already in an event loop: schedule fire-and-forget
        asyncio.create_task(send_telegram_async(text, parse_mode=parse_mode))
