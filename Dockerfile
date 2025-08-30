FROM python:3.10-slim

WORKDIR /app

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY backend/ ./backend

# Nginx 설치
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Nginx 설정 복사
COPY nginx.conf /etc/nginx/nginx.conf

ENV PORT=8000
EXPOSE 8000

# Django(5000), Flask(5001) 실행 + Nginx 프록시
CMD gunicorn backend.wsgi:application -b 0.0.0.0:5000 & \
    gunicorn backend.app:app -b 0.0.0.0:5001 & \
    nginx -g 'daemon off;'
