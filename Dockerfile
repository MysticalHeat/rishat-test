FROM python:3.13-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-dev --no-install-project

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN uv run python manage.py collectstatic --noinput


FROM python:3.13-slim-bookworm

RUN groupadd --system rishat && useradd --system --gid rishat rishat

RUN install -d -o rishat -g rishat /data
VOLUME /data

WORKDIR /app

COPY --from=build --chown=rishat:rishat /app/.venv /app/.venv
COPY --from=build --chown=rishat:rishat /app/staticfiles /app/staticfiles
COPY --chown=rishat:rishat manage.py /app/manage.py
COPY --chown=rishat:rishat config /app/config
COPY --chown=rishat:rishat app /app/app

RUN chown -R rishat:rishat /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

USER rishat

EXPOSE 8000

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "4", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
