import os
import time
import logging
import threading
import asyncio
from pathlib import Path

import yaml
import pdfplumber
from dotenv import load_dotenv

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from telegram import Bot

from google import genai

# ============================================================
# Global async loop (Telegram)
# ============================================================

ASYNC_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(ASYNC_LOOP)


def start_async_loop():
    ASYNC_LOOP.run_forever()


# ============================================================
# Environment & Config
# ============================================================

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"

load_dotenv()


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# Logging
# ============================================================

def setup_logging(config: dict):
    logging.basicConfig(
        level=getattr(logging, config["logging"]["level"]),
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(config["logging"]["file"], encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


# ============================================================
# File Reading
# ============================================================

def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> str:
    text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text)


def read_file(path: Path, max_chars: int) -> str:
    if path.suffix.lower() == ".pdf":
        content = read_pdf_file(path)
    else:
        content = read_text_file(path)

    return content[:max_chars].strip()


# ============================================================
# Gemini
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai_client = genai.Client(api_key=GEMINI_API_KEY)


def analyze_with_gemini(text: str, config: dict) -> str:
    model_name = config["ai"]["model"]
    prompt = config["ai"]["prompt"]

    response = genai_client.models.generate_content(
        model=model_name,
        contents=f"{prompt}\n\n{text}"
    )

    if not response or not response.text:
        raise RuntimeError("Empty Gemini response")

    return response.text.strip()


# ============================================================
# Telegram (v20+ async)
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

tg_bot = Bot(token=TELEGRAM_TOKEN)


def telegram_enabled(config: dict) -> bool:
    return (
        config.get("telegram", {}).get("enabled", False)
        and TELEGRAM_TOKEN
        and TELEGRAM_CHAT_ID
    )


async def _send_to_telegram_async(message: str):
    await tg_bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message
    )


def send_to_telegram(message: str, max_len: int):
    if len(message) > max_len:
        message = message[: max_len - 3] + "..."

    try:
        ASYNC_LOOP.call_soon_threadsafe(
            asyncio.create_task,
            _send_to_telegram_async(message)
        )
        logging.info("Telegram task scheduled")

    except Exception as e:
        logging.error(f"Telegram error: {e}")


def format_telegram_message(path: Path, ai_text: str) -> str:
    return f"📄 {path.name}\n\n{ai_text}"


# ============================================================
# Watchdog Handler
# ============================================================

class FileHandler(FileSystemEventHandler):
    def __init__(self, config: dict):
        self.config = config
        self.extensions = set(config["monitor"]["extensions"])
        self.max_chars = config["files"]["max_chars"]

    def on_created(self, event):
        self.process(event)

    def on_modified(self, event):
        self.process(event)

    def process(self, event):
        if event.is_directory:
            return

        path = Path(event.src_path)

        if path.suffix.lower() not in self.extensions:
            return

        if self.config["monitor"].get("ignore_hidden", True):
            if path.name.startswith("."):
                return

        logging.info(f"File changed: {path}")

        try:
            text = read_file(path, self.max_chars)

            if not text:
                logging.info("Empty file, skipped")
                return

            logging.info(f"Read {len(text)} characters")

            ai_result = analyze_with_gemini(text, self.config)
            logging.info("AI analysis completed")

            if telegram_enabled(self.config):
                message = format_telegram_message(path, ai_result)
                send_to_telegram(
                    message,
                    self.config["telegram"]["max_message_length"]
                )

        except Exception:
            logging.exception(f"Error processing file: {path}")


# ============================================================
# Main
# ============================================================

def main():
    print("Starting Folder AI Monitor (MVP)")

    config = load_config()
    setup_logging(config)

    threading.Thread(
        target=start_async_loop,
        daemon=True
    ).start()

    watch_path = Path(config["monitor"]["watch_path"])
    logging.info(f"Watching folder: {watch_path}")

    observer = Observer()
    observer.schedule(
        FileHandler(config),
        watch_path,
        recursive=True
    )

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopping monitor...")
        observer.stop()

    observer.join()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()
