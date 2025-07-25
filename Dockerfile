# Use an official Playwright Docker image with Python and browser dependencies
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
# Playwright itself and its browsers are already included in the base image.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY stock_bot.py .

# Expose the port that Flask will run on (Render usually detects this, but good practice)
EXPOSE 10000

# Command to run the application
# This will start your Flask server, which then starts the bot in a separate thread.
CMD ["python", "stock_bot.py"]