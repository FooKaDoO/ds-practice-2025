FROM python:3.11

WORKDIR /app

# Copy the requirements file
COPY ./books/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start the transaction verification service
CMD ["python", "books/src/app.py"]