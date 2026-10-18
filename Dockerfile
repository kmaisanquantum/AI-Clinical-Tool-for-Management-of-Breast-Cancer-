FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput || true
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health/'%os.environ.get('PORT','8000'),timeout=4)" || exit 1
CMD ["sh", "entrypoint.sh", "gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--access-logfile", "-", \
     "--log-level", "info"]
