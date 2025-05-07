FROM python:3.11

WORKDIR /app

# Copy the requirements file
COPY ./payments/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start the transaction verification service
CMD python utils/other/hotreload.py "payments/src/app.py"
