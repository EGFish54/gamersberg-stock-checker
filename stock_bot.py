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
TARGET_SEEDS = ["Beanstalk", "Burning Bud", "Giant Pinecone", "Sugar Apple", "Ember Lily"]
GMAIL_SENDER_EMAIL = os.environ.get("GMAIL_SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GMAIL_RECIPIENT_EMAIL = os.environ.get("GMAIL_RECIPIENT_EMAIL")
ENABLE_GMAIL_EMAIL = os.environ.get("ENABLE_GMAIL_EMAIL", "False").lower() == "true"
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "120"))

notified_seeds = set()

def send_email_notification(subject, body):
    if not ENABLE_GMAIL_EMAIL:
        logger.info("Email disabled.")
        return
    if not GMAIL_SENDER_EMAIL or not GMAIL_APP_PASSWORD or not GMAIL_RECIPIENT_EMAIL:
        logger.warning("Incomplete email config.")
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
        logger.error(f"Error sending email: {e}", exc_info=True)

async def check_stock_async():
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, timeout=90000)
            page = await browser.new_page()
            await page.goto(WEBSITE_URL, wait_until="networkidle", timeout=90000)
            await page.wait_for_selector(".seed-item", timeout=90000)
            seed_items = await page.locator(".see_
