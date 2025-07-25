import os
import asyncio
import re
import smtplib
from email.message import EmailMessage
from playwright.async_api import async_playwright, TimeoutError
import threading
import time
from flask import Flask, jsonify
import traceback 

print("--- DEBUG: Script execution started! ---") # Keep this for early diagnostic

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
GMAIL_SENDER_EMAIL = os.environ.get("GMAIL_SENDER_EMAIL")       # Your Gmail address (the sender)
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")       # Your Gmail App Password
GMAIL_RECIPIENT_EMAIL = os.environ.get("GMAIL_RECIPIENT_EMAIL") # The email address to send alerts to

ENABLE_GMAIL_EMAIL = os.environ.get("ENABLE_GMAIL_EMAIL", "False").lower() == "true"
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "120")) # Default to 2 minutes

# Global variable to keep track of notified seeds across checks
notified_seeds = set()

def send_email_notification(subject, body):
    """Sends an email notification using Gmail SMTP."""
    if not ENABLE_GMAIL_EMAIL:
        print("Gmail email is disabled. Skipping email sending.")
        return

    if not GMAIL_SENDER_EMAIL or not GMAIL_APP_PASSWORD or not GMAIL_RECIPIENT_EMAIL:
        print("Gmail credentials or recipient email not fully configured. Cannot send email.")
        return

    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = GMAIL_SENDER_EMAIL
        msg['To'] = GMAIL_RECIPIENT_EMAIL

        print(f"Attempting to send email to {GMAIL_RECIPIENT_EMAIL}...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
        print("Please ensure you've generated an App Password for your Gmail account if you have 2FA enabled.")
        print("You can generate one here: https://myaccount.google.com/apppasswords")
        traceback.print_exc()


async def check_stock_async():
    """Asynchronously checks the website for target seed stock and sends alerts."""
    print(f"Starting stock check for {WEBSITE_URL}...")
    print(f"Target seeds: {', '.join(TARGET_SEEDS)}")

    print("--- DEBUG: Before async_playwright context ---")
    async with async_playwright() as p:
        print("--- DEBUG: Inside async_playwright context ---")
        browser = None
        try:
            print("Attempting to launch Chromium browser...")
            # ADDED: dumpio=True to output browser process logs
            browser = await p.chromium.launch(headless=True, timeout=60000) 
            print("Chromium browser launched successfully.")
            page = await browser.new_page()
            print(f"Navigating to {WEBSITE_URL}...")
            await page.goto(WEBSITE_URL, wait_until="networkidle", timeout=60000)
            print("Page loaded via goto. Waiting for selector '.seed-item'...")

            try:
                await page.wait_for_selector(".seed-item", timeout=60000)
                print("Selector '.seed-item' found. Extracting elements...")
            except TimeoutError:
                print(f"Timeout: Selector '.seed-item' not found within 60 seconds. Attempting to get page content for inspection...")
                page_content = await page.content()
                print("--- Start of Page Content (first 2000 chars) ---")
                print(page_content[:2000])
                print("--- End of Page Content ---")
                raise # Re-raise the TimeoutError so it's still caught by the outer except block

            seed_items = await page.locator(".seed-item").all()
            print(f"Found {len(seed_items)} seed items.")
            
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
                    print(f"Processing {cleaned_seed_name}: Stock: {quantity}")
                    if quantity > 0 and cleaned_seed_name not in notified_seeds:
                        newly_available_seeds.append(f"{cleaned_seed_name}: {quantity} available!")
                        notified_seeds.add(cleaned_seed_name) 

            if newly_available_seeds:
                alert_email_subject = "Gamersberg Stock Alert! NEWLY AVAILABLE!"
                alert_email_body = "The following target seeds are now available:\n\n" + "\n".join(newly_available_seeds)
                print("Sending availability alert via email...")
                send_email_notification(alert_email_subject, alert_email_body.strip())
            else:
                print("No *newly* available target seeds found in stock.")

        except TimeoutError as te:
            print(f"Final Timeout Error during stock check: {te}")
            print(f"Error: Page elements did not load within the expected time for {WEBSITE_URL}. This might indicate the page structure changed, network issues, or the website being slow to respond.")
            traceback.print_exc()
        except Exception as e:
            print(f"An unexpected error occurred during stock check: {e}")
            traceback.print_exc()
        finally:
            if browser:
                await browser.close()
                print("Chromium browser closed.")
    print("Stock check completed.")


def run_bot_in_background():
    """Runs the stock check indefinitely in an asyncio event loop."""
    print("Starting background stock checker loop...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        loop.run_until_complete(check_stock_async())
        print(f"Waiting for {CHECK_INTERVAL_SECONDS} seconds before next check...")
        time.sleep(CHECK_INTERVAL_SECONDS) 

# --- Flask Web Server ---
app = Flask(__name__)

@app.route('/')
def home():
    """A simple endpoint for Render to ping."""
    return jsonify({"status": "ok", "message": "Gamersberg Stock Bot is running!"})

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    print("Starting Gamersberg Stock Bot application...")
    bot_thread = threading.Thread(target=run_bot_in_background)
    bot_thread.daemon = True 
    bot_thread.start()

    port = int(os.environ.get("PORT", 8080))
    print(f"Flask server starting on port {port}")
    app.run(host="0.0.0.0", port=port)
