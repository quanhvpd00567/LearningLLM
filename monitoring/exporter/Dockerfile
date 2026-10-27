FROM python:3.12-slim
WORKDIR /exporter
RUN pip install --no-cache-dir prometheus-client==0.23.1
COPY exporter.py .
CMD ["python", "-u", "exporter.py"]
