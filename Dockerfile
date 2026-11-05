FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home journal
COPY . .
RUN SECRET_KEY=build-only-placeholder DEBUG=true python manage.py collectstatic --noinput && chown -R journal:journal /app
USER journal
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--access-logformat", "%(h)s %(m)s %(U)s %(s)s", "--error-logfile", "-"]
