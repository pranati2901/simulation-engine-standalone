# Goalcert Scenario Engine — API image (ECS Fargate).
#
# SCOPE: this image serves the API ONLY. The federated frontend (remoteEntry.js +
# assets/style.css) is published to S3/CloudFront by CI — see AWS_DEPLOYMENT.md. Locally
# the same code serves frontend/dist at "/" when it is present (app/main.py checks), which
# is why there is no frontend build stage here: on AWS that directory is absent by design
# and main.py falls back cleanly.
#
# The engine must be reachable ONLY through the hub's gateway (private subnet + SG). Its
# multi-tenancy trusts the X-Goalcert-Org header, which is only trustworthy because the
# gateway is the sole ingress — and because SCENARIO_API_KEY is set. Unset, verify_api_key
# allows everything and tenancy becomes decoration.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8002

WORKDIR /app

# Dependencies first so a code change doesn't rebust the pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Run unprivileged. ECS won't enforce this for you.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Documentation only — ECS uses the task definition's portMappings. $PORT is what matters,
# and awsvpc mode sets it; the default keeps `docker run` working unchanged.
EXPOSE 8002

# Container-level check. The ALB target group has its own check on the same path — this one
# is what ECS uses to restart a wedged task even before the LB notices.
# /health is public (core/auth.py exempts it) so it works with SCENARIO_API_KEY set.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8002'), timeout=4).status==200 else 1)"

# exec form via sh -c so ${PORT} expands. Single worker per task: scale with ECS desired
# count, not uvicorn workers — see the run-graph note in AWS_DEPLOYMENT.md before raising
# the task count above 1.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8002} --proxy-headers --forwarded-allow-ips='*'"]
