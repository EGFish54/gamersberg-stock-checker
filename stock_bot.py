import os
import logging
from flask import Flask, jsonify

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("--- DEBUG: Simple Flask app started! ---")

# --- Flask Web Server ---
app = Flask(__name__)

@app.route("/")
def home():
    logger.info("Root path accessed.")
    return jsonify({"status": "ok", "message": "Simple Gamersberg Stock Bot is running. Logs should be visible."})

@app.route("/health")
def health():
    logger.info("Health check accessed.")
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    logger.info("--- DEBUG: Main execution block for simple Flask app started! ---")
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Flask server starting on port {port}")
    app.run(host="0.0.0.0", port=port)
