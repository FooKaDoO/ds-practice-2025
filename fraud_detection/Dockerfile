# Use an official Python runtime as the base image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

# Copy the entire fraud_detection directory, including ml_model.py
COPY ./fraud_detection /app/fraud_detection

# Set working directory inside the fraud_detection folder
WORKDIR /app/fraud_detection

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Default command (for running the fraud detection service)
CMD ["python", "src/app.py"]
