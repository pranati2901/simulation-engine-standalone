# R5 hack-lab goal app — MediumCorp SecureMail (intentionally vulnerable, training range only).
FROM python:3.11-slim
RUN pip install --no-cache-dir flask==3.0.3 && apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app.py /app/app.py
EXPOSE 80
CMD ["python", "app.py"]
