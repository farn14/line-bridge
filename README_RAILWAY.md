# 🚀 คู่มือการนำ Personal LINE Bridge ขึ้นรันบน Railway ตลอด 24 ชั่วโมง

ระบบนี้ถูกออกแบบให้ **Portable 100%** โดยฝังการเชื่อมต่อ E2EE Keys, Auto-Fallback, และ Healthcheck Web Server สำหรับ Railway เรียบร้อยแล้ว

---

## 🛠️ ขั้นตอนที่ 1: นำโฟลเดอร์นี้ขึ้น GitHub (แบบ Private)

1. เปิด PowerShell หรือ Git Bash ที่โฟลเดอร์ `C:\Users\gsose\Desktop\line_bridge`
2. สร้าง Git Repository:
   ```bash
   git init
   git add .
   git commit -m "feat: personal line bridge for railway"
   ```
3. สร้าง Repository ใหม่บน GitHub (แนะนำให้ตั้งเป็น **Private**) เช่นชื่อ `line-bridge`
4. ผูก Remote และ Push ขึ้น GitHub:
   ```bash
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/line-bridge.git
   git branch -M main
   git push -u origin main
   ```

---

## ☁️ ขั้นตอนที่ 2: เชื่อมต่อและ Deploy บน Railway

1. ล็อกอินเข้า [Railway.app](https://railway.app)
2. กด **"+ New Project"** > เลือก **"Deploy from GitHub repo"**
3. เลือก Repository `line-bridge` ที่เพิ่ง Push ขึ้นไป
4. Railway จะตรวจจับ `Dockerfile` และเริ่ม Build Image ให้อัตโนมัติ

---

## ⚙️ ขั้นตอนที่ 3: ตั้งค่าตัวแปร (Variables) บน Railway

เข้าไปที่แท็บ **Variables** ใน Project บน Railway แล้วเพิ่มตัวแปรดังนี้:

| Variable Name | Value | หมายเหตุ |
| :--- | :--- | :--- |
| `AUTH_TOKEN` | `eyJ0eXAiOiJKV1QiLC...` | ใช้ Token ปัจจุบันที่ได้จากการสแกน (คัดลอกจาก config.json) |
| `GROUP_A_ID` | `c0123456789abcdef0123456789abcdef` | ID กลุ่มต้นทาง A (คัดลอกจาก config.json) |
| `GROUP_B_ID` | `c9876543210fedcba9876543210fedcba` | ID กลุ่ม/บอทปลายทาง B (คัดลอกจาก config.json) |
| `TIMEOUT_SECONDS` | `90` | ตั้งเวลารอผลลัพธ์ 90 วินาที (1.30 นาที) |

> 💡 **หมายเหตุเรื่อง Healthcheck**:
> โค้ด `2_run_bridge.py` มี Web Server ขนาดเล็กตรวจจับ `$PORT` ของ Railway อยู่ในตัว ทำให้ Railway ตรวจสอบสถานะว่าระบบออนไลน์ (Healthy) ตลอด 24 ชม. ไม่ถูกสั่งตัดการทำงาน

---

## 🔄 ขั้นตอนที่ 4: การต่ออายุ Token (เมื่อ Token หมดอายุในอนาคต)

- Secondary Desktop Token ของ LINE มีอายุใช้งานประมาณ 7 วัน ถึง 1 เดือน
- หากระบบบน Railway แจ้งเตือน Token หมดอายุ:
  1. ดับเบิลคลิก `1_LOGIN.bat` บนเครื่องคอมเพื่อสแกน QR ใหม่
  2. ก๊อปปี้ `AuthToken` ใหม่ที่ได้
  3. ไปที่ Railway > แท็บ **Variables** > อัปเดตค่า `AUTH_TOKEN`
  4. Railway จะ Restart และทำงานต่อทันที ไม่ต้องแก้โค้ดใหม่
