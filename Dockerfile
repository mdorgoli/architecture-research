FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8000
WORKDIR /app
COPY expense-manager/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 app
COPY --chown=app:app expense-manager/ /app/
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/staticfiles && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health/live/', timeout=3)"
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
