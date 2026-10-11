# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

FROM ${PYTHON_IMAGE} AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv     && /opt/venv/bin/pip install --only-binary=:all: -r requirements.txt

FROM ${PYTHON_IMAGE} AS translations
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements-i18n.txt .
RUN pip install --only-binary=:all: -r requirements-i18n.txt
COPY scripts/compile_translations.py scripts/compile_translations.py
COPY locales locales
RUN python scripts/compile_translations.py

FROM ${PYTHON_IMAGE} AS runtime
LABEL org.opencontainers.image.source="https://github.com/mdorgoli/architecture-research"
ENV PATH="/opt/venv/bin:$PATH"     PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     DATABASE_URL="sqlite:////data/expenses.db"     APP_ORIGIN="https://localhost:8443"
RUN groupadd --gid 10001 app     && useradd --uid 10001 --gid app --no-create-home app     && mkdir /data && chown app:app /data
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY --from=translations /build/locales /app/locales
COPY main.py auth.py security.py settings.py database.py models.py schemas.py i18n.py create_user.py alembic.ini ./
COPY alembic alembic
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3     CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
