FROM python:3.10-slim

WORKDIR /app

# ติดตั้ง Dependencies สำหรับ C Extensions และ Network
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ติดตั้ง Dependencies ทั้งหมดก่อน แล้วค่อยติดตั้ง CHRLINE แบบ --no-deps เพื่อเลี่ยงข้อขัดแย้งของ pycryptodome 3.9.8 เดิม
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --no-deps CHRLINE==2.5.14

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "2_run_bridge.py"]
