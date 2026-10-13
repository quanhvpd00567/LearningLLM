FROM python:3.11-slim

WORKDIR /app

# Cài torch CPU TRƯỚC — pin version, force CPU index
RUN pip install --no-cache-dir \
    "torch==2.7.0+cpu" \
    --index-url https://download.pytorch.org/whl/cpu

# sentence-transformers sẽ thấy torch đã có, không pull lại từ PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health', timeout=5)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
