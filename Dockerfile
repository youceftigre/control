FROM python:3.12-slim

# مكتبات النظام لـ WeasyPrint + خطوط عربية احترافية
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-naskh-arabic \
    fonts-noto-sans-arabic \
    fonts-amiri \
    fonts-kacst \
    fonts-sil-scheherazade \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت التبعيات أوّلاً (طبقة قابلة للتخزين المؤقت)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# مجلّد للقاعدة + اللوغات على الـ disk mount
RUN mkdir -p /data /app/logs && chmod 777 /data /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
# إن لم تستعمل قاعدة PostgreSQL، نخزّن SQLite على الـ disk mount
ENV DATABASE_URL=sqlite:////data/exams.db

# Render يضبط $PORT تلقائياً (10000 افتراضاً)
EXPOSE 10000
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT:-10000} \
    --timeout 120 \
    --workers 2 \
    --access-logfile - \
    --error-logfile -
