# Use an official Python runtime as a parent image
FROM python:3.9-slim-bookworm

# Install system dependencies for Playwright browsers
# Playwright requires certain libraries to run browsers in a headless environment.
# The 'install-deps' command is part of the playwright package.
RUN pip install playwright && playwright install --with-deps

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY requirements.txt .
COPY stock_bot.py .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the application
# This will execute your Python script directly
CMD ["python", "stock_bot.py"]