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

# ... (rest of your configuration and send_email_notification function) ...

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
            browser = await p.chromium.launch(headless=True, timeout=60000, dumpio=True) 
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

# ... (rest of your run_bot_in_background and Flask app code) ...
