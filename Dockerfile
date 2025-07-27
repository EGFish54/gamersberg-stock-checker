FROM python:3.11-slim

WORKDIR /app

# Install OS packages needed by Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg unzip fonts-liberation libnss3 libatk-bridge2.0-0 libgtk-3-0 \
    libxss1 libasound2 libxshmfence1 libgbm1 libxrandr2 libxdamage1 libxcomposite1 libxext6 libxfixes3 libxi6 libxtst6 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy bot code
COPY . .

EXPOSE 10000
CMD ["python", "stock_bot.py"]
