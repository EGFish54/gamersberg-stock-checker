import os
import asyncio
import re
import smtplib
from email.message import EmailMessage
from playwright.async_api import async_playwright, TimeoutError
import threading
import time
# Flask imports are removed for now for debugging
import traceback
import logging # Import logging module

# Configure logging to output to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("--- DEBUG: Script execution started! ---") # Use logger instead of print

# --- Configuration (using environment variables) ---
WEBSITE_URL = os.environ.get("WEBSITE_URL", "https://www.gamersberg.com/grow-a-garden/stock")

# The seeds you are looking for (case-insensitive search)
TARGET_SEEDS = [
    "Beanstalk",
    "Burning Bud",
    "Giant Pinecone",
    "Sugar Apple",
    "Ember Lily"
]

# Gmail Configuration (Set these as environment variables)
GMAIL_SENDER_EMAIL = os.environ.get("GMAIL_SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_RECIPIENT_EMAIL = os.environ.get("GMAIL_RECIPIENT_EMAIL")

ENABLE_GMAIL_EMAIL = os.environ.get("ENABLE_GMAIL_EMAIL", "False").lower() == "true"
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "120"))

# Global variable to keep track of notified seeds across checks
notified_seeds = set()

def send_email_notification(subject, body):
    """Sends an email notification using Gmail SMTP."""
    if not ENABLE_GMAIL_EMAIL:
        logger.info("Gmail email is disabled. Skipping email sending.")
        return

    if not GMAIL_SENDER_EMAIL or not GMAIL_APP_PASSWORD or not GMAIL_RECIPIENT_EMAIL:
        logger.warning("Gmail credentials or recipient email not fully configured. Cannot send email.")
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
        logger.info("Email sent successfully!")
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True) # exc_info=True prints traceback
        logger.error("Please ensure you've generated an App Password for your Gmail account if you have 2FA enabled.")
        logger.error("You can generate one here: https://myaccount.google.com/apppasswords")


async def check_stock_async():
    """Asynchronously checks the website for target seed stock and sends alerts."""
    logger.info(f"Starting stock check for {WEBSITE_URL}...")
    logger.info(f"Target seeds: {', '.join(TARGET_SEEDS)}")

    logger.info("--- DEBUG: Before async_playwright context ---")
    async with async_playwright() as p:
        logger.info("--- DEBUG: Inside async_playwright context ---")
        browser = None
        try:
            logger.info("Attempting to launch Chromium browser...")
            browser = await p.chromium.launch(headless=True, timeout=60000)
            logger.info("Chromium browser launched successfully.")
            page = await browser.new_page()
            logger.info(f"Navigating to {WEBSITE_URL}...")
            await page.goto(WEBSITE_URL, wait_until="networkidle", timeout=60000)
            logger.info("Page loaded via goto. Waiting for selector '.seed-item'...")

            try:
                await page.wait_for_selector(".seed-item", timeout=60000)
                logger.info("Selector '.seed-item' found. Extracting elements...")
            except TimeoutError:
                logger.warning(f"Timeout: Selector '.seed-item' not found within 60 seconds. Attempting to get page content for inspection...")
                page_content = await page.content()
                logger.info("--- Start of Page Content (first 2000 chars) ---")
                logger.info(page_content[:2000])
                logger.info("--- End of Page Content ---")
                raise # Re-raise the TimeoutError

            seed_items = await page.locator(".seed-item").all()
            logger.info(f"Found {len(seed_items)} seed items.")
            
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
                    logger.info(f"Processing {cleaned_seed_name}: Stock: {quantity}")
                    if quantity > 0 and cleaned_seed_name not in notified_seeds:
                        newly_available_seeds.append(f"{cleaned_seed_name}: {quantity} available!")
                        notified_seeds.add(cleaned_seed_name)

            if newly_available_seeds:
                alert_email_subject = "Gamersberg Stock Alert! NEWLY AVAILABLE!"
                alert_email_body = "The following target seeds are now available:\n\n" + "\n".join(newly_available_seeds)
                logger.info("Sending availability alert via email...")
                send_email_notification(alert_email_subject, alert_email_body.strip())
            else:
                logger.info("No *newly* available target seeds found in stock.")

        except TimeoutError as te:
            logger.error(f"Final Timeout Error during stock check: {te}", exc_info=True)
            logger.error(f"Error: Page elements did not load within the expected time for {WEBSITE_URL}. This might indicate the page structure changed, network issues, or the website being slow to respond.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during stock check: {e}", exc_info=True)
        finally:
            if browser:
                await browser.close()
                logger.info("Chromium browser closed.")
    logger.info("Stock check completed.")


def run_bot_in_background():
    """Runs the stock check indefinitely in an asyncio event loop."""
    logger.info("Starting background stock checker loop...") # Use logger here too
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try: # Add a try/except around the async call as well
            loop.run_until_complete(check_stock_async())
        except Exception as e:
            logger.error(f"Error in background stock checker loop: {e}", exc_info=True)
            # Potentially add a short sleep here to prevent rapid error looping
        logger.info(f"Waiting for {CHECK_INTERVAL_SECONDS} seconds before next check...")
        time.sleep(CHECK_INTERVAL_SECONDS)

# --- TEMPORARILY REMOVED FLASK FOR DEBUGGING ---
# app = Flask(__name__)
# @app.route('/')
# def home():
#     return jsonify({"status": "ok", "message": "Gamersberg Stock Bot is running!"})
# @app.route('/health')
# def health_check():
#     return jsonify({"status": "healthy"})

if __name__ == "__main__":
    logger.info("--- DEBUG: Main execution block started! ---") # New diagnostic print
    try:
        # We will directly run the bot in the main thread for now, without Flask
        # This simplifies the execution environment significantly for debugging.
        run_bot_in_background()
    except Exception as e:
        logger.error(f"--- DEBUG: Critical error in main execution block: {e}", exc_info=True)
