FROM python:3.11

WORKDIR /app

# Copy the requirements file
COPY ./suggestions/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start the suggestions service
CMD python utils/other/hotreload.py "suggestions/src/app.py"
