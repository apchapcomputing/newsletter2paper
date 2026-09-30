"""
Signal bot using bbernhard/signal-cli-rest-api as a bridge.

Setup:
1. Register or link a Signal number in the signal-cli container first:
   docker exec -it signal-cli signal-cli -u +15551234567 register
   docker exec -it signal-cli signal-cli -u +15551234567 verify <CODE>
2. Set SIGNAL_NUMBER env var to that phone number (e.g. +15551234567).

The bot polls /v1/receive for incoming messages and replies via /v2/send.
"""

import os
import re
import time
import logging
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
from shared.api_client import APIClient

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r'https?://[^\s]+')
# Per-sender layout preference: {sender_number: "essay"|"newspaper"}
sender_layouts: dict = {}


def send_signal_message(signal_url: str, number: str, recipient: str, message: str) -> None:
    with httpx.Client(timeout=30) as client:
        client.post(
            f"{signal_url}/v2/send",
            json={"message": message, "number": number, "recipients": [recipient]},
        )


def receive_messages(signal_url: str, number: str) -> list:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{signal_url}/v1/receive/{number}")
        if resp.status_code == 200:
            return resp.json() or []
    return []


async def handle_url(url: str, sender: str, api: APIClient, signal_url: str, number: str) -> None:
    layout = sender_layouts.get(sender, "essay")
    send_signal_message(signal_url, number, sender, f"Converting article… (layout: {layout})")
    try:
        result = await api.convert_article(url, layout_type=layout)
        if result.get("success") and result.get("pdf_url"):
            send_signal_message(signal_url, number, sender, f"Done! Download your PDF:\n{result['pdf_url']}")
        else:
            send_signal_message(signal_url, number, sender, "Conversion failed. Please check the URL and try again.")
    except Exception as e:
        send_signal_message(signal_url, number, sender, f"Error: {e}")


def process_message(msg: dict, api: APIClient, signal_url: str, number: str) -> None:
    import asyncio
    envelope = msg.get("envelope", {})
    data_message = envelope.get("dataMessage", {})
    sender = envelope.get("source", "")
    text = data_message.get("message", "") or ""

    if not text or not sender:
        return

    # Handle layout command
    if text.startswith("/layout "):
        layout_type = text.split(maxsplit=1)[1].strip()
        if layout_type in ("essay", "newspaper"):
            sender_layouts[sender] = layout_type
            send_signal_message(signal_url, number, sender, f"Layout set to: {layout_type}")
        else:
            send_signal_message(signal_url, number, sender, "Usage: /layout essay  or  /layout newspaper")
        return

    if text.strip() in ("/help", "/start"):
        send_signal_message(
            signal_url, number, sender,
            "Newsletter2Paper Bot\nSend me any article URL to convert it to a printable PDF.\n\n"
            "/layout essay — single-column essay (default)\n"
            "/layout newspaper — three-column newspaper style"
        )
        return

    urls = _URL_RE.findall(text)
    if urls:
        asyncio.run(handle_url(urls[0], sender, api, signal_url, number))


def main() -> None:
    number = os.environ["SIGNAL_NUMBER"]
    signal_url = os.environ.get("SIGNAL_CLI_URL", "http://signal-cli:8080")
    fastapi_url = os.environ.get("FASTAPI_BASE_URL", "http://fastapi:8000")
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "5"))

    api = APIClient(fastapi_url)
    logger.info(f"Signal bot polling as {number} (interval: {poll_interval}s)…")

    while True:
        try:
            messages = receive_messages(signal_url, number)
            for msg in messages:
                process_message(msg, api, signal_url, number)
        except Exception as e:
            logger.error(f"Poll error: {e}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
