# W1 hack-lab goal app — Mercy Health Patient Portal (intentionally vulnerable, training range only).
FROM python:3.11-slim
RUN pip install --no-cache-dir flask==3.0.3
WORKDIR /app
COPY app.py /app/app.py
EXPOSE 80
CMD ["python", "app.py"]
