import os
import asyncio
import re
import smtplib
from email.message import EmailMessage
from playwright.async_api import async_playwright, TimeoutError
import threading
import time
import traceback
import logging
from flask import Flask, jsonify

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://www.gamersberg.com/grow-a-garden/stock")
TARGET_SEEDS = ["Beanstalk", "Burning Bud", "Giant Pinecone", "Sugar Apple", "Tomato", "Elder Strawberry","Ember Lily"]
GMAIL_SENDER_EMAIL = os.environ.get("GMAIL_SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_RECIPIENT_EMAIL = os.environ.get("GMAIL_RECIPIENT_EMAIL")
ENABLE_GMAIL_EMAIL = os.environ.get("ENABLE_GMAIL_EMAIL", "False").lower() == "true"
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "120"))

notified_seeds = set()

def send_email_notification(subject, body):
    if not ENABLE_GMAIL_EMAIL:
        logger.info("Email sending disabled.")
        return
    if not GMAIL_SENDER_EMAIL or not GMAIL_APP_PASSWORD or not GMAIL_RECIPIENT_EMAIL:
        logger.warning("Incomplete Gmail config.")
        return
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = GMAIL_SENDER_EMAIL
        msg['To'] = GMAIL_RECIPIENT_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info("Email sent.")
    except Exception as e:
        logger.error("Failed to send email.", exc_info=True)

async def check_stock_async():
    async with async_playwright() as p:
        browser = None
        try:
            logger.info(f"Checking stock at {WEBSITE_URL}...")
            browser = await p.chromium.launch(headless=True, timeout=90000)
            page = await browser.new_page()
            await page.goto(WEBSITE_URL, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(3000)  # Wait 3 seconds
            await page.wait_for_selector("div.bg-gradient-to-br.rounded-lg.border-blue-400\/30.backdrop-blur-md", timeout=90000)
            seed_items = await page.locator("div.bg-gradient-to-br.rounded-lg.border-blue-400\/30.backdrop-blur-md").all()
            logger.info(f"Found {len(seed_items)} seed items on page.")

            newly_available_seeds = []

            for item_element in seed_items:
                seed_name_element = item_element.locator("h2")
                stock_element = item_element.locator("p.text-green-500, p.text-red-500")

                seed_name = await seed_name_element.text_content()
                stock_text = await stock_element.text_content()

                cleaned_seed_name = seed_name.replace(" Seed", "").strip()
                match = re.search(r'Stock:\s*(\d+)', stock_text)
                quantity = int(match.group(1)) if match else 0

                if cleaned_seed_name in TARGET_SEEDS:
                    logger.info(f"{cleaned_seed_name}: {quantity} in stock")
                    if quantity > 0 and cleaned_seed_name not in notified_seeds:
                        newly_available_seeds.append(f"{cleaned_seed_name}: {quantity} available!")
                        notified_seeds.add(cleaned_seed_name)

            if newly_available_seeds:
                send_email_notification(
                    "Gamersberg Stock Alert! NEWLY AVAILABLE!",
                    "\n".join(newly_available_seeds)
                )
            else:
                logger.info("No new target seeds available.")

        except TimeoutError:
            logger.warning("Timeout during Playwright scraping.")
        except Exception as e:
            logger.error("Unexpected error during scraping.", exc_info=True)
        finally:
            if browser:
                await browser.close()

def run_stock_checker_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            loop.run_until_complete(check_stock_async())
        except Exception as e:
            logger.error("Error in loop.", exc_info=True)
        time.sleep(CHECK_INTERVAL_SECONDS)

# --- Flask Web Server (required for Render) ---
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Gamersberg Stock Bot is running."})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    threading.Thread(target=run_stock_checker_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
