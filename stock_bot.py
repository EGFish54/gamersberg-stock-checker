import os
import asyncio
import re
import smtplib
from email.message import EmailMessage
from playwright.async_api import async_playwright, TimeoutError

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
# CHECK_INTERVAL_SECONDS is no longer needed as the Render Cron Job handles the scheduling.

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


async def check_stock():
    """Checks the website for target seed stock and sends alerts."""
    print(f"Starting stock check for {WEBSITE_URL}...")
    print(f"Target seeds: {', '.join(TARGET_SEEDS)}")

    async with async_playwright() as p:
        browser = None
        try:
            # Run in headless mode for deployment
            browser = await p.chromium.launch(headless=True) 
            page = await browser.new_page()
            await page.goto(WEBSITE_URL, wait_until="domcontentloaded")

            # Wait for the seed items to be present
            # Increased timeout for initial load
            await page.wait_for_selector(".seed-item", timeout=15000) 

            seed_items = await page.locator(".seed-item").all()
            found_available_seeds = False
            alert_email_subject = "Gamersberg Stock Alert!"
            alert_email_body = "The following target seeds are now available:\n\n"

            for item_element in seed_items:
                seed_name_element = item_element.locator("h2")
                stock_element = item_element.locator("p.text-green-500, p.text-red-500")

                seed_name = await seed_name_element.text_content()
                stock_text = await stock_element.text_content()

                # Clean up seed name to match target list (e.g., remove " Seed")
                cleaned_seed_name = seed_name.replace(" Seed", "").strip()

                # Extract quantity using regex
                match = re.search(r'Stock:\s*(\d+)', stock_text)
                quantity = int(match.group(1)) if match else 0

                if cleaned_seed_name in TARGET_SEEDS:
                    print(f"Found {cleaned_seed_name}: Stock: {quantity}")
                    if quantity > 0:
                        alert_email_body += f"- {cleaned_seed_name}: {quantity} available!\n"
                        found_available_seeds = True

            if found_available_seeds:
                print("Sending availability alert via email...")
                send_email_notification(alert_email_subject, alert_email_body.strip())
            else:
                print("No target seeds found available in stock.")

        except TimeoutError:
            print(f"Error: Page elements did not load within the expected time for {WEBSITE_URL}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            if browser:
                await browser.close()
    print("Stock check completed.")

# The script will now run check_stock() once and then exit.
# Render's Cron Job will handle the repeated execution.
if __name__ == "__main__":
    print("Starting bot...")
    asyncio.run(check_stock())
