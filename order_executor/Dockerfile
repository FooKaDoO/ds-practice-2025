FROM python:3.11

WORKDIR /app

# Copy the requirements file
COPY ./order_executor/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start the transaction verification service
CMD python utils/other/hotreload.py "order_executor/src/app.py"
