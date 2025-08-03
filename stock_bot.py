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
from flask import Flask, jsonify # Flask imports re-enabled

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("--- DEBUG: Script execution started! ---")

# --- Configuration ---
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://www.gamersberg.com/grow-a-garden/stock")
# Added Tomato and Elder Strawberry from your latest update
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
        logger.info(f"Attempting to send email to {GMAIL_RECIPIENT_EMAIL}...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info("Email sent.")
    except Exception as e:
        logger.error("Failed to send email.", exc_info=True)
        logger.error("Please ensure you've generated an App Password for your Gmail account if you have 2FA enabled.")
        logger.error("You can generate one here: https://myaccount.google.com/apppasswords")

async def check_stock_async():
    async with async_playwright() as p:
        browser = None
        try:
            logger.info(f"Checking stock at {WEBSITE_URL}...")
            # Using 90s timeout for browser launch
            browser = await p.chromium.launch(
                headless=True,
                timeout=90000,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-video-decode',
                    '--disable-gpu',
                    '--single-process'
                ]
            )
            page = await browser.new_page()

            # Increased page.goto timeout to 90s (same as browser launch) and added a 45s hard wait
            logger.info(f"Navigating to {WEBSITE_URL}, waiting for DOM content to load, then a 45s pause for full rendering...")
            await page.goto(WEBSITE_URL, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(45000)  # Increased wait to 45 seconds for full page rendering

            logger.info("Waiting for main seed item containers...")
            # Using your new, more specific selector for the main containers
            seed_item_container_selector = "div.bg-gradient-to-br.rounded-lg.border-blue-400\/30.backdrop-blur-md"
            await page.wait_for_selector(seed_item_container_selector, timeout=90000)
            logger.info(f"Main seed item containers found. Retrieving all items with selector: {seed_item_container_selector}")

            seed_items = await page.locator(seed_item_container_selector).all()
            logger.info(f"Found {len(seed_items)} seed items on page.")

            newly_available_seeds = []

            for i, item_element in enumerate(seed_items):
                logger.info(f"Processing item {i+1}/{len(seed_items)}...")
                # NEW: Add a small pause for elements within each item to settle
                await page.wait_for_timeout(5000) # Wait 5 seconds for sub-elements to fully render/become stable

                try:
                    # Explicitly wait for h2 and p elements to be visible within THIS item
                    seed_name_element = item_element.locator("h2")
                    await seed_name_element.wait_for(state="visible", timeout=60000) # Increased to 60 seconds
                    seed_name = await seed_name_element.text_content()
                    logger.info(f"Extracted name for item {i+1}: {seed_name}")

                    stock_element = item_element.locator("p.text-green-500, p.text-red-500")
                    await stock_element.wait_for(state="visible", timeout=60000) # Increased to 60 seconds
                    stock_text = await stock_element.text_content()
                    logger.info(f"Extracted stock text for item {i+1}: {stock_text}")

                    cleaned_seed_name = seed_name.replace(" Seed", "").strip()
                    match = re.search(r'Stock:\s*(\d+)', stock_text)
                    quantity = int(match.group(1)) if match else 0

                    if cleaned_seed_name in TARGET_SEEDS:
                        logger.info(f"{cleaned_seed_name}: {quantity} in stock")
                        if quantity > 0 and cleaned_seed_name not in notified_seeds:
                            newly_available_seeds.append(f"{cleaned_seed_name}: {quantity} available!")
                            notified_seeds.add(cleaned_seed_name)
                except TimeoutError as e:
                    logger.warning(f"Timeout while processing elements for item {i+1}. Skipping this item. Error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error extracting data for item {i+1}: {e}", exc_info=True)
                    continue


            if newly_available_seeds:
                send_email_notification(
                    "Gamersberg Stock Alert! NEWLY AVAILABLE!",
                    "\n".join(newly_available_seeds)
                )
            else:
                logger.info("No new target seeds available.")

        except TimeoutError as te:
            logger.error(f"Global Timeout during Playwright scraping (initial page load or main selector): {te}", exc_info=True)
            logger.error("This means the page or main selector did not load in time.")
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
        finally:
            if browser:
                await browser.close()
                logger.info("Chromium browser closed.")
    logger.info("Stock check completed.")

def run_stock_checker_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            loop.run_until_complete(check_stock_async())
        except Exception as e:
            logger.error("Error in background stock checker loop.", exc_info=True)
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
    logger.info("--- DEBUG: Main execution block started! ---\n") # Added newline for clarity in logs
    try:
        # Start the stock checker in a separate thread so Flask can run in the main thread
        threading.Thread(target=run_stock_checker_loop, daemon=True).start()

        # Start the Flask web server
        port = int(os.environ.get("PORT", 10000)) # Use environment PORT or default to 10000
        logger.info(f"Flask server starting on port {port}")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"--- DEBUG: Critical error in main execution block (Flask or Threading issue): {e}", exc_info=True)
