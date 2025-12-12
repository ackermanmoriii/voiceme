# استفاده از نسخه سبک و پایدار پایتون
FROM python:3.10-slim

# تنظیم دایرکتوری کاری داخل کانتینر
WORKDIR /app

# جلوگیری از تولید فایل‌های کش پایتون (pyc) برای کاهش حجم
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# کپی و نصب نیازمندی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کل کدها به داخل کانتینر
COPY . .

# پورت استاندارد Zeabur
EXPOSE 8080

# اجرای ربات با استفاده از سرور قدرتمند Gunicorn
# (این دستور ربات را روی پورت 8080 اجرا می‌کند)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120"]
