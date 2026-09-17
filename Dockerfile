FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY constraints/python312.txt ./constraints/python312.txt
COPY app ./app
COPY evals ./evals
COPY data ./data
COPY docs ./docs

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -c constraints/python312.txt .

# Keep the runtime identity stable so bind-mounted Product Core and backup
# directories can be owned by one documented, non-root UID/GID.
RUN groupadd --gid 10001 opencare \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin opencare \
    && mkdir -p /app/data /app/reports /run/opencare \
        /var/lib/opencare/product-core /var/backups/opencare \
    && chown -R 10001:10001 /app/data /app/reports /run/opencare \
        /var/lib/opencare/product-core /var/backups/opencare

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
