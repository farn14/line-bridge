# -*- coding: utf-8 -*-
"""
สคริปต์สะพานเชื่อมระหว่างกลุ่ม A และกลุ่ม B (Personal LINE Bridge)
ความเร็วระดับ Sub-second (< 0.2 - 0.3 วินาที) ด้วย High-Speed Direct Polling + E2EE
รองรับการรันทั้งบน Local PC (Windows) และ Cloud Platform (Railway / Docker 24/7)
"""
import os
import sys
import re
import time
import threading
from CHRLINE import CHRLINE

# ========================================================
# ⚙️ ข้อมูลการเชื่อมต่อระบบ (ดึงจาก Env ก่อน หรือใช้ค่า Default)
# ========================================================
AUTH_TOKEN = os.getenv(
    "AUTH_TOKEN",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiI5ZDlhYTljYS1hMmVlLTRlZDktYjRmOC0wMTM1MzJhMWY0MmMiLCJhdWQiOiJMSU5FIiwiaWF0IjoxNzkxMzYyNTAzLCJleHAiOjE3OTE5NjczMDMsInNjcCI6IkxJTkVfQ09SRSIsInJ0aWQiOiI4ZWYzZmM4Ny0wYmNkLTRjNmItYTg1NS01YThjYzU0Mjk1YjkiLCJyZXhwIjoxODIyODk4NTAzLCJ2ZXIiOiIzLjAiLCJhaWQiOiJ1MmQ1ZjM4NTU4NjM2YmI2ZWZkOGEzZTI2MWZiZWQ4YWIiLCJsc2lkIjoiNGU0ZDFmODYtMmMxZC00Y2RhLWEyYmEtMTJjZTBhODNiYjA5IiwiZGlkIjoiTk9ORSIsImN0eXBlIjoiREVTS1RPUF9XSU4iLCJjbW9kZSI6IlNFQ09OREFSWSIsImNpZCI6IjAxMDAwMDAwMDAifQ.OUr_dfAteyhP_AsYeRqgVeOxmnElV4nfGj2WAyNWBRY"
)

GROUP_A_ID = os.getenv("GROUP_A_ID", "ca64a75009f7db17537dede906b49beed")  # กลุ่มA
GROUP_B_ID = os.getenv("GROUP_B_ID", "cecf0ffbb255456787662d7190a24b160")  # กลุ่มB
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "90"))  # 1.30 นาที (90 วินาที)

# โหลดค่าจาก config.json (ถ้ามี)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
saved_cfg = {}
if os.path.exists(CONFIG_FILE):
    try:
        import json
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved_cfg = json.load(f)
            AUTH_TOKEN = os.getenv("AUTH_TOKEN", saved_cfg.get("auth_token", AUTH_TOKEN))
            GROUP_A_ID = os.getenv("GROUP_A_ID", saved_cfg.get("group_a_id", GROUP_A_ID))
            GROUP_B_ID = os.getenv("GROUP_B_ID", saved_cfg.get("group_b_id", GROUP_B_ID))
            TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", str(saved_cfg.get("timeout_seconds", TIMEOUT_SECONDS))))
    except Exception:
        pass

# -------------------------------------------------------------
# ระบบ Proxy Gateway มุดการเชื่อมต่อ (แก้ปัญหา 403 Forbidden บน Cloud/Railway)
# รองรับทั้ง LINE_PROXY, HTTPS_PROXY, HTTP_PROXY (http, https, socks5)
# -------------------------------------------------------------
PROXY_URL = (os.getenv("LINE_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or saved_cfg.get("proxy_url", "")).strip()
if PROXY_URL:
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
    os.environ["ALL_PROXY"] = PROXY_URL
    
    try:
        import requests
        _orig_req_init = requests.Session.__init__
        def _patched_req_init(self, *args, **kwargs):
            _orig_req_init(self, *args, **kwargs)
            self.proxies = {"http": PROXY_URL, "https": PROXY_URL}
        requests.Session.__init__ = _patched_req_init
        
        import httpx
        _orig_httpx_init = httpx.Client.__init__
        def _patched_httpx_init(self, *args, **kwargs):
            if "proxy" not in kwargs and "proxies" not in kwargs:
                kwargs["proxy"] = PROXY_URL
            return _orig_httpx_init(self, *args, **kwargs)
        httpx.Client.__init__ = _patched_httpx_init
        
        clean_proxy = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL.split("://")[-1]
        print(f"🛡️ เปิดใช้งาน Proxy เพื่อเลี่ยง 403 LEGY: {clean_proxy}")
    except Exception as e:
        print(f"⚠️ ตั้งค่า Proxy Interceptor: {e}")

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.15"))  # ความถี่ในการตรวจสอบข้อความ (วินาที)
PORT = int(os.getenv("PORT", "0"))  # สำหรับ Railway Health Check
# ========================================================

PENDING_REQUESTS = {}
BOT_REPLIES_SENT = set()
SEEN_A = set()
SEEN_B = set()
LOCK = threading.Lock()

print("=" * 65)
print("🌉 กำลังเริ่มระบบ Personal LINE Bridge (กลุ่ม A <---> กลุ่ม B)...")
print(f"⏱️ ตั้งค่า Timeout ไว้ที่: {TIMEOUT_SECONDS} วินาที (1.30 นาที)")
print("=" * 65)

# เปิด Healthcheck Web Server ถ้ามี PORT (สำหรับ Railway)
if PORT > 0:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"personal-line-bridge","uptime":"active"}')
        def log_message(self, format, *args):
            pass

    def run_health_server():
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        server.serve_forever()

    threading.Thread(target=run_health_server, daemon=True).start()
    print(f"🌐 Railway Healthcheck Server ออนไลน์บนพอร์ต {PORT}")

try:
    cl = CHRLINE(authTokenOrEmail=AUTH_TOKEN, device="DESKTOPWIN", version="9.2.0.3421")
    my_profile = cl.getProfile()
    my_mid = cl.checkAndGetValue(my_profile, 1, 'mid') or getattr(cl, 'mid', '') or 'u2d5f38558636bb6efd8a3e261fbed8ab'
    my_name = cl.checkAndGetValue(my_profile, 20, 'displayName') or 'ผู้ใช้ LINE'
    
    # ฝัง E2EE Key อัตโนมัติ (Portable: รองรับทั้งบัญชีใหม่, Windows, และ Railway/Docker)
    try:
        from base64 import b64decode
        e2ee_cfg = saved_cfg.get("e2ee_keys", {})
        if e2ee_cfg and "privKey" in e2ee_cfg and "pubKey" in e2ee_cfg:
            k_id = e2ee_cfg.get("keyId", 6058564)
            k_ver = e2ee_cfg.get("e2eeVersion", 1)
            priv_k = b64decode(e2ee_cfg["privKey"])
            pub_k = b64decode(e2ee_cfg["pubKey"])
            cl.saveE2EESelfKeyData(my_mid, pub_k, priv_k, k_id, k_ver)
        else:
            PRIV_KEY = b' \xe1\xe8\x13&+~YC\x19\xbe\x07\x04\xc6\xf0M\xaf\xfb=\x15\x05"\x13X\xb9\xffy\xa0\xf6\xaa3V'
            PUB_KEY = b"P\xd6\xdb\xe8\x8bG>\x97\xd3\xa0,\xe1W\xb1\xb4U\xe3\x0bx\xb1R\xcfK\xe5\x15?e\xca\xce\x1f'T"
            cl.saveE2EESelfKeyData(my_mid, PUB_KEY, PRIV_KEY, 6058564, 1)
    except Exception as e:
        pass

    g_a_name = saved_cfg.get("group_a_name", "กลุ่มA")
    g_b_name = saved_cfg.get("group_b_name", "กลุ่มB")
    target_b_type = saved_cfg.get("group_b_type", "OA/USER" if str(GROUP_B_ID).startswith("u") else "GROUP")
    print(f"✅ บัญชีคน A ออนไลน์แล้ว: {my_name} (MID: {my_mid})")
    print(f"📍 ต้นทาง A  : {g_a_name} ({GROUP_A_ID})")
    print(f"📍 ปลายทาง B ({target_b_type}): {g_b_name} ({GROUP_B_ID})")
    print("⚡ ระบบ High-Speed Direct Polling (< 0.2 วินาที) พร้อมทำงานแล้ว!")
    print("=" * 65)
except Exception as e:
    print(f"❌ เข้าสู่ระบบล้มเหลว: {e}")
    sys.exit(1)

def extract_text(msg):
    """ถอดรหัสข้อความรองรับทั้ง Plain Text, LINE OA และ E2EE (Letter Sealing)"""
    text = msg.get(10) or ''
    meta = msg.get(18) or {}
    if not text and isinstance(meta, dict):
        if 'e2eeVersion' in meta:
            try:
                text = cl.decryptE2EETextMessage(msg)
            except Exception:
                pass
        elif 'text' in meta:
            text = meta.get('text', '')
    return text or ''

def send_msg(to_mid, text):
    """ส่งข้อความ: หากปลายทางเป็น LINE OA/User (u...) ให้ส่งแบบ Plain ทันทีเพื่อความเร็วระดับ Milliseconds"""
    if str(to_mid).startswith('u'):
        try:
            return cl.sendMessage(to_mid, text)
        except Exception:
            return cl.sendMessageWithE2EE(to_mid, text)
    else:
        try:
            return cl.sendMessageWithE2EE(to_mid, text)
        except Exception:
            return cl.sendMessage(to_mid, text)

# เริ่มต้นจดจำ Message ID เก่าในทั้งสองกลุ่ม เพื่อไม่ให้ยิงข้อความเก่าซ้ำ
try:
    for m in cl.getRecentMessagesV2(GROUP_A_ID, 10) or []:
        if m.get(4):
            SEEN_A.add(m.get(4))
    for m in cl.getRecentMessagesV2(GROUP_B_ID, 10) or []:
        if m.get(4):
            SEEN_B.add(m.get(4))
    print(f"📦 โหลดประวัติข้อความเดิมเรียบร้อย (พร้อมตรวจจับข้อความใหม่ทันที)")
except Exception as e:
    print(f"⚠️ โหลดประวัติเริ่มต้น: {e}")

# Thread ดูแล Timeout เคลียร์คิวที่เกิน 1.30 นาที (90 วินาที)
def watchdog_loop():
    while True:
        time.sleep(5)
        now = time.time()
        expired = []
        with LOCK:
            for target_key, data in list(PENDING_REQUESTS.items()):
                if now - data["timestamp"] > TIMEOUT_SECONDS:
                    expired.append(target_key)
            for target_key in expired:
                del PENDING_REQUESTS[target_key]
                print(f"⏱️ [Timeout] รหัส/หมายเลข '{target_key}' รอเกิน {TIMEOUT_SECONDS} วินาที (1.30 นาที) ไม่มีคำตอบจากกลุ่ม B (ล้างคิว)")

threading.Thread(target=watchdog_loop, daemon=True).start()

print("👂 กำลังดักฟังข้อความในทั้ง 2 กลุ่มแบบ Real-time... (กด Ctrl+C เพื่อหยุด)")

def extract_target_key(text):
    """
    สกัดหมายเลขเป้าหมายสำหรับทำ Correlation Key
    รองรับทั้ง:
    - เลขประจำตัวประชาชน 13 หลัก (เช่น 1234567812324 หรือ 1-2345-67812-32-4)
    - เบอร์โทรศัพท์ 9-10 หลัก (เช่น 0821519172, 021234567)
    - เลขบัญชี / หมายเลขอ้างอิง 6-18 หลัก
    - หรือพารามิเตอร์ที่ตามหลังเครื่องหมาย #, $, %
    """
    # 1. ค้นหาตัวเลขต่อเนื่องความยาว 6 ถึง 18 หลัก
    m = re.search(r'\d{6,18}', text)
    if m:
        return m.group(0)
        
    # 2. กรณีตัวเลขมีขีดคั่น เช่น 1-2345-67812-32-4 หรือ 081-234-5678
    digits = re.sub(r'\D', '', text)
    if 6 <= len(digits) <= 18:
        return digits
        
    # 3. สกัดพารามิเตอร์ที่อยู่ติดหรือตามหลัง #, $, %
    p = re.search(r'[#\$%]\s*([a-zA-Z0-9\-_]+)', text)
    if p:
        return p.group(1)
        
    return None

while True:
    try:
        # ====================================================
        # 1. ตรวจสอบ "กลุ่ม A" (ข้อความคำสั่งจากผู้ใช้หรือตัวเอง)
        # ====================================================
        recent_a = cl.getRecentMessagesV2(GROUP_A_ID, 5) or []
        new_msgs_a = [m for m in recent_a if m.get(4) and m.get(4) not in SEEN_A]
        
        # จัดเรียงจากเก่าไปใหม่ เพื่อส่งตามลำดับที่พิมพ์จริง
        new_msgs_a.reverse()
        for msg in new_msgs_a:
            msg_id = msg.get(4)
            sender = msg.get(1) or ""
            SEEN_A.add(msg_id)
            if len(SEEN_A) > 1000:
                SEEN_A.pop()
                
            text = extract_text(msg).strip()
            if not text:
                continue
                
            # ข้ามข้อความที่บอทเราเพิ่งดีดกลับมาตอบในกลุ่ม A
            if text in BOT_REPLIES_SENT:
                BOT_REPLIES_SENT.discard(text)
                continue
                
            print(f"🔔 [ข้อความใหม่ในกลุ่ม A] '{text}'")
            
            # 🛡️ เงื่อนไขสำคัญ: ข้อความต้องมีเครื่องหมาย # หรือ $ หรือ % เท่านั้น ถ้าไม่มีคือห้ามส่งเด็ดขาด
            TRIGGER_SYMBOLS = ['#', '$', '%']
            if not any(sym in text for sym in TRIGGER_SYMBOLS):
                # ข้อความทั่วไปที่ไม่มีสัญลักษณ์คำสั่ง (#, $, %) จะไม่ถูกส่งไปกลุ่ม B
                continue

            # สกัดหมายเลขเป้าหมาย (รองรับทั้ง 13 หลัก, 10 หลัก, และเลขอื่นๆ)
            target_key = extract_target_key(text)
            if target_key:
                print(f"📥 [ตรวจพบคำสั่งที่มี {', '.join(TRIGGER_SYMBOLS)}] '{text}' | Target Key: {target_key}")
                
                with LOCK:
                    PENDING_REQUESTS[target_key] = {
                        "source_group": GROUP_A_ID,
                        "timestamp": time.time(),
                        "cmd": text
                    }
                    
                # ดีดคำสั่งเข้าปลายทาง B ทันที
                try:
                    send_msg(GROUP_B_ID, text)
                    print(f"⚡ [ยิงไปปลายทาง B ({target_b_type}) สำเร็จ]: '{text}'")
                except Exception as e:
                    print(f"❌ ยิงเข้าปลายทาง B ล้มเหลว: {e}")
            else:
                print(f"ℹ️ มีสัญลักษณ์คำสั่ง (#, $, %) แต่ไม่พบหมายเลขหรือพารามิเตอร์: '{text}' (ไม่ส่งไปปลายทาง B)")

        # ====================================================
        # 2. ตรวจสอบ "ปลายทาง B" (คำตอบจากบอท Master หรือ LINE OA)
        # ====================================================
        recent_b = cl.getRecentMessagesV2(GROUP_B_ID, 5) or []
        new_msgs_b = [m for m in recent_b if m.get(4) and m.get(4) not in SEEN_B]
        
        new_msgs_b.reverse()
        for msg in new_msgs_b:
            msg_id = msg.get(4)
            sender = msg.get(1) or ""
            SEEN_B.add(msg_id)
            if len(SEEN_B) > 1000:
                SEEN_B.pop()
                
            # ถ้าเป็นข้อความที่ตัวเองส่งไปในปลายทาง B ให้ข้าม
            if sender == my_mid:
                continue
                
            text = extract_text(msg).strip()
            if not text:
                continue
                
            print(f"🔔 [ข้อความใหม่ในปลายทาง B ({target_b_type})] จาก {sender}: '{text[:60]}...'")
            
            matched_target = None
            source_group = None
            clean_reply_digits = re.sub(r'\D', '', text)

            with LOCK:
                for target_key, data in list(PENDING_REQUESTS.items()):
                    # ตรวจจับทั้งแบบมีขีดคั่น, ไม่มีขีดคั่น, หรือข้อความตรงๆ
                    if target_key in text or (target_key.isdigit() and target_key in clean_reply_digits):
                        matched_target = target_key
                        source_group = data["source_group"]
                        del PENDING_REQUESTS[target_key]
                        break
                        
            if matched_target and source_group:
                print(f"🎯 [ปลายทาง B ({target_b_type}) ตอบกลับแล้ว!] พบข้อมูลตรงกับ Target: {matched_target}")
                try:
                    BOT_REPLIES_SENT.add(text)
                    send_msg(source_group, text)
                    print(f"🚀 [ดีดผลลัพธ์กลับกลุ่ม A สำเร็จเรียบร้อย!]")
                except Exception as e:
                    print(f"❌ ส่งกลับกลุ่ม A ล้มเหลว: {e}")

        time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 หยุดการทำงานระบบ Personal LINE Bridge เรียบร้อยแล้ว")
        break
    except Exception as e:
        time.sleep(1)
