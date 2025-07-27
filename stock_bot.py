import os
import logging
import time
import threading
from flask import Flask
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Configuration
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO", EMAIL_USER)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 120))  # seconds
PORT = int(os.getenv("PORT", 10000))
TARGET_URL = "https://www.gamersberg.com/grow-a-garden/stock"

# Seeds you're looking for
TARGET_SEEDS = [
    "Banana",
    "Watermelon",
    "Melon",
    "Strawberry",
    "Blueberry",
    "Kiwi",
    "Grapes",
]

# Track last seen availability
last_available = set()

# Flask app
app = Flask(__name__)

@app.route("/")
def index():
    return "👀 Gamersberg Stock Checker is running."

def send_email(subject, body):
    logging.info(f"Sending email to {EMAIL_TO}")
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        logging.info("✅ Email sent.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

async def check_stock_async():
    logging.info(f"Checking stock at {TARGET_URL}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()

            try:
                await page.goto(TARGET_URL, timeout=60000)

                # Adjusted selector based on your working Selenium logic
                selector = "div.bg-gradient-to-br.rounded-lg.border-blue-400\\/30.backdrop-blur-md"
                await page.wait_for_selector(selector, timeout=90000)

                seed_items = await page.locator(selector).all()
                logging.info(f"✅ Found {len(seed_items)} seed items.")

                available = set()

                for item in seed_items:
                    text = await item.inner_text()
                    for seed in TARGET_SEEDS:
                        if seed.lower() in text.lower():
                            available.add(seed)

                logging.info(f"Available seeds found: {available}")

                # Check if there's anything new
                new_items = available - last_available
                if new_items:
                    subject = "🌱 New Gamersberg Seeds Available!"
                    body = f"The following seeds are now available:\n\n" + "\n".join(sorted(new_items))
                    send_email(subject, body)
                    last_available.clear()
                    last_available.update(available)

            except PlaywrightTimeout:
                logging.warning("Timeout during Playwright scraping.")

            await context.close()
            await browser.close()

    except Exception as e:
        logging.error(f"Scraping error: {e}")

def stock_checker_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        loop.run_until_complete(check_stock_async())
        logging.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

def start_background_thread():
    thread = threading.Thread(target=stock_checker_loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    start_background_thread()
    app.run(host="0.0.0.0", port=PORT)
