FROM python:3.12-slim

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/ Backend/
COPY Frontend/ Frontend/

WORKDIR /app/Backend

EXPOSE 8000

CMD ["uvicorn", "v1:app", "--host", "0.0.0.0", "--port", "8000"]
