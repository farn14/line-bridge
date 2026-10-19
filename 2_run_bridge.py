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
import collections
try:
    import gevent.monkey
except ImportError:
    import types
    _g = types.ModuleType("gevent")
    _m = types.ModuleType("gevent.monkey")
    _m.patch_all = lambda *a, **k: None
    _g.monkey = _m
    _g.sleep = time.sleep
    sys.modules["gevent"] = _g
    sys.modules["gevent.monkey"] = _m
from CHRLINE import CHRLINE

# ========================================================
# ⚙️ ข้อมูลการเชื่อมต่อระบบ (ดึงจาก Env ก่อน หรือโหลดจาก config.json)
# ========================================================
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "").strip()
GROUP_A_ID = os.getenv("GROUP_A_ID", "").strip()
GROUP_B_ID = os.getenv("GROUP_B_ID", "").strip()
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "90"))  # 1.30 นาที (90 วินาที)

# โหลดค่าจาก config.json (ถ้ามี)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
saved_cfg = {}
if os.path.exists(CONFIG_FILE):
    try:
        import json
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved_cfg = json.load(f)
            if not AUTH_TOKEN:
                AUTH_TOKEN = str(saved_cfg.get("auth_token", "")).strip()
            if not GROUP_A_ID:
                GROUP_A_ID = str(saved_cfg.get("group_a_id", "")).strip()
            if not GROUP_B_ID:
                GROUP_B_ID = str(saved_cfg.get("group_b_id", "")).strip()
            if "timeout_seconds" in saved_cfg and not os.getenv("TIMEOUT_SECONDS"):
                TIMEOUT_SECONDS = int(saved_cfg.get("timeout_seconds", 90))
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการอ่าน config.json: {e}")

# รายชื่อสมาชิก/แอดมินที่ได้รับอนุญาตให้ส่งคำสั่ง (Whitelist) - ถ้าไม่ระบุคืออนุญาตเฉพาะตัวเอง (my_mid)
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", "").strip() or str(saved_cfg.get("allowed_users", "")).strip()
ALLOWED_USERS = set(filter(None, [u.strip() for u in ALLOWED_USERS_RAW.split(",")])) if ALLOWED_USERS_RAW else set()

# รายชื่อบอท Master ในกลุ่ม B (ถ้าไม่ระบุจะใช้วิธีตรวจจับบอทอัตโนมัติ)
MASTER_BOT_MIDS_RAW = os.getenv("MASTER_BOT_MIDS", "").strip() or str(saved_cfg.get("master_bot_mids", "")).strip()
MASTER_BOT_MIDS = set(filter(None, [b.strip() for b in MASTER_BOT_MIDS_RAW.split(",")])) if MASTER_BOT_MIDS_RAW else set()

if not AUTH_TOKEN or not GROUP_B_ID:
    print("=" * 65)
    print("⚠️ ยังไม่ได้เข้าสู่ระบบหรือตั้งค่ากลุ่ม LINE สำหรับ Bridge")
    print("=" * 65)
    print("ไม่พบ Token หรือ ID กลุ่ม LINE ปลายทาง B ใน config.json")
    print("\n👉 วิธีเริ่มใช้งาน:")
    print("1. รันไฟล์ '1_LOGIN.bat' เพื่อสแกน QR Code และเลือกกลุ่มที่ต้องการเชื่อมต่อ")
    print("2. ระบบจะสร้างไฟล์ config.json ให้อัตโนมัติ จากนั้นรัน '2_RUN_BRIDGE.bat' ได้ทันที")
    print("=" * 65)
    sys.exit(1)

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

class Deduplicator:
    def __init__(self, maxlen=1000):
        self.q = collections.deque(maxlen=maxlen)
        self.s = set()
        self._lock = threading.Lock()
    def add(self, item):
        with self._lock:
            if item in self.s:
                return False
            if len(self.q) == self.q.maxlen:
                self.s.discard(self.q.popleft())
            self.q.append(item)
            self.s.add(item)
            return True
    def discard(self, item):
        with self._lock:
            self.s.discard(item)
    def __contains__(self, item):
        with self._lock:
            return item in self.s
    def __len__(self):
        with self._lock:
            return len(self.s)

PENDING_REQUESTS = {}
BOT_REPLIES_SENT = Deduplicator(maxlen=2000)
HUMAN_SENDERS_B = Deduplicator(maxlen=5000)  # บันทึก MID ของผู้ใช้ทั่วไปในกลุ่ม B เพื่อแยกแยะไม่ให้สับสนกับบอท (Bounded ป้องกัน Memory Leak)
SEEN_A = Deduplicator(maxlen=1000)
SEEN_B = Deduplicator(maxlen=1000)
SEEN_PRIVATE = Deduplicator(maxlen=2000)
LOCK = threading.Lock()
START_TIME = time.time()
METRICS = {
    "routed_a_to_b": 0,
    "routed_b_to_dest": 0,
    "last_poll_ts": time.time(),
    "consecutive_errors": 0
}

print("=" * 65)
print("🌉 กำลังเริ่มระบบ Personal LINE Bridge (กลุ่ม A <---> กลุ่ม B)...")
print(f"⏱️ ตั้งค่า Timeout ไว้ที่: {TIMEOUT_SECONDS} วินาที (1.30 นาที)")
print("=" * 65)

# เปิด Healthcheck Web Server ถ้ามี PORT (สำหรับ Railway / Live Metrics)
if PORT > 0:
    import json
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            with LOCK:
                pending_count = len(PENDING_REQUESTS)
            uptime_sec = int(time.time() - START_TIME)
            status_data = {
                "status": "ok",
                "service": "personal-line-bridge",
                "uptime_seconds": uptime_sec,
                "pending_queue_size": pending_count,
                "routed_a_to_b": METRICS["routed_a_to_b"],
                "routed_b_to_dest": METRICS["routed_b_to_dest"],
                "seen_a_size": len(SEEN_A),
                "seen_b_size": len(SEEN_B),
                "seen_private_size": len(SEEN_PRIVATE)
            }
            body = json.dumps(status_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
    my_mid = cl.checkAndGetValue(my_profile, 1, 'mid') or getattr(cl, 'mid', '') or ''
    my_name = cl.checkAndGetValue(my_profile, 20, 'displayName') or 'ผู้ใช้ LINE'
    
    # ฝัง E2EE Key อัตโนมัติ (Portable: รองรับทั้งบัญชีใหม่, Windows, และ Railway/Docker)
    try:
        from base64 import b64decode
        e2ee_cfg = saved_cfg.get("e2ee_keys", {})
        if e2ee_cfg and "privKey" in e2ee_cfg and "pubKey" in e2ee_cfg:
            k_id = int(e2ee_cfg.get("keyId", 0))
            k_ver = int(e2ee_cfg.get("e2eeVersion", 1))
            priv_k = b64decode(e2ee_cfg["privKey"])
            pub_k = b64decode(e2ee_cfg["pubKey"])
            cl.saveE2EESelfKeyData(my_mid, pub_k, priv_k, k_id, k_ver)
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
    """ถอดรหัสข้อความรองรับทั้ง Plain Text, LINE OA และ E2EE (Letter Sealing) ทั้งในกลุ่มและแชทส่วนตัว 1:1"""
    text = msg.get(10) or ''
    meta = msg.get(18) or {}
    if not text:
        if (isinstance(meta, dict) and 'e2eeVersion' in meta) or msg.get(20):
            is_self = (msg.get(1) == my_mid)
            try:
                text = cl.decryptE2EETextMessage(msg, isSelf=is_self)
            except Exception:
                try:
                    text = cl.decryptE2EETextMessage(msg, isSelf=not is_self)
                except Exception:
                    pass
        elif isinstance(meta, dict) and 'text' in meta:
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

# เริ่มต้นจดจำ Message ID เก่าในกลุ่มปลายทางและกลุ่ม A (ถ้ามี) เพื่อไม่ให้ยิงข้อความเก่าซ้ำ
try:
    if GROUP_A_ID:
        for m in cl.getRecentMessagesV2(GROUP_A_ID, 15) or []:
            if m.get(4):
                SEEN_A.add(m.get(4))
    for m in cl.getRecentMessagesV2(GROUP_B_ID, 15) or []:
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
    - หรือพารามิเตอร์ที่ตามหลังเครื่องหมาย #, $, % (รองรับภาษาไทย)
    """
    # 1. ค้นหาตัวเลขต่อเนื่องความยาว 6 ถึง 18 หลัก
    m = re.search(r'\d{6,18}', text)
    if m:
        return m.group(0)
        
    # 2. กรณีตัวเลขมีขีดคั่น เช่น 1-2345-67812-32-4 หรือ 081-234-5678
    digits = re.sub(r'\D', '', text)
    if 6 <= len(digits) <= 18:
        return digits
        
    # 3. สกัดพารามิเตอร์ที่อยู่ติดหรือตามหลัง #, $, % (แก้ไขรองรับภาษาไทย)
    p = re.search(r'[#\$%]\s*([^\s]+)', text)
    if p:
        return p.group(1)
        
    return None

def private_msg_loop():
    """เธรดดักฟังข้อความแชทส่วนตัว 1:1 Direct Message แบบ Real-time ผ่าน LINE Push Ops"""
    print("👂 เปิดเธรดดักฟังแชทส่วนตัว (1:1 Direct Message) แบบ Real-time...")
    try:
        if not hasattr(cl, 'revision') or not cl.revision:
            cl.revision = cl.getLastOpRevision()
        print(f"📡 [Private Listener] เริ่มต้นดักฟังที่ Op Revision: {cl.revision}")
    except Exception as e:
        print(f"⚠️ [Private Listener] ดึง Op Revision เริ่มต้นล้มเหลว: {e}")
        cl.revision = 0

    while True:
        try:
            ops = cl.fetchOps(cl.revision, count=50)
            if not ops:
                time.sleep(0.3)
                continue
                
            for op in ops:
                op_type = cl.checkAndGetValue(op, 'type', 3) or op.get(3)
                op_rev = cl.checkAndGetValue(op, 'revision', 1) or op.get(1)
                if op_rev:
                    cl.setRevision(op_rev)
                    
                # สนใจเฉพาะข้อความเข้า 26 (RECEIVE_MESSAGE) หรือที่เราส่งเอง 25 (SEND_MESSAGE)
                if op_type not in (25, 26):
                    continue
                    
                msg = cl.checkAndGetValue(op, 'message', 20) or op.get(20) or {}
                if not msg:
                    continue
                    
                msg_id = msg.get(4)
                if not msg_id or msg_id in SEEN_PRIVATE:
                    continue
                SEEN_PRIVATE.add(msg_id)
                
                # จำแนกประเภทห้องแชท (0 = แชทส่วนตัว 1:1, 1 = ห้องแชทหลายคน, 2 = กลุ่ม)
                to_type = cl.checkAndGetValue(msg, 'toType', 3) or msg.get(3)
                to_mid = msg.get(2) or ""
                sender = msg.get(1) or ""

                # ข้ามข้อความทั้งหมดที่เกิดขึ้นในกลุ่มปลายทาง B เพื่อป้องกันลูปวนกลับ (กลุ่ม B มีลูปตรวจสอบคำตอบแยกต่างหาก)
                if to_mid == GROUP_B_ID:
                    continue

                # คำนวณเป้าหมายสำหรับตอบกลับ:
                # - ถ้าเป็นกลุ่ม (to_type == 2 หรือขึ้นต้นด้วย c): กลุ่มต้นทางคือ to_mid
                # - ถ้าเป็นแชทส่วนตัว 1:1 (ขึ้นต้นด้วย u): ถ้าเพื่อนทักมา reply_target คือ sender, ถ้าเราพิมพ์เอง reply_target คือ to_mid
                if to_type == 2 or str(to_mid).startswith('c'):
                    reply_target = to_mid
                    chat_label = f"กลุ่ม {to_mid[:10]}..."
                else:
                    reply_target = sender if sender != my_mid else to_mid
                    chat_label = f"แชทส่วนตัว 1:1 จาก {sender[:10]}..."

                if not reply_target:
                    continue

                text = extract_text(msg).strip()
                if not text:
                    continue

                # ข้ามข้อความที่บอทเพิ่งดีดกลับมาตอบ
                with LOCK:
                    if text in BOT_REPLIES_SENT:
                        BOT_REPLIES_SENT.discard(text)
                        continue

                # กรองคำสั่ง: ต้องมีสัญลักษณ์ # หรือ $ หรือ %
                TRIGGER_SYMBOLS = ['#', '$', '%']
                if not any(sym in text for sym in TRIGGER_SYMBOLS):
                    continue

                # 🛡️ [Access Control / Anti-Spoofing]: ตรวจสอบสิทธิ์ผู้ส่งคำสั่ง
                # ถ้ามีการกำหนด ALLOWED_USERS ผู้ส่งต้องอยู่ใน whitelist หรือเป็นตัวเอง (my_mid)
                # ถ้าไม่ได้กำหนด ALLOWED_USERS อนุญาตให้ทุกคนในกลุ่มส่งได้ แต่แชท 1:1 ต้องเป็นตัวเองเท่านั้น
                is_authorized = False
                if ALLOWED_USERS:
                    is_authorized = (sender in ALLOWED_USERS or sender == my_mid)
                else:
                    is_authorized = (to_type == 2 or str(to_mid).startswith('c') or sender == my_mid)

                if not is_authorized:
                    print(f"⛔ [สกัดกั้นคำสั่งที่ไม่ได้รับอนุญาต] จาก {sender} ({chat_label}): '{text}'")
                    continue

                target_key = extract_target_key(text)
                if target_key:
                    print(f"📥 [ตรวจพบคำสั่งจาก {chat_label}] '{text}' | Target Key: {target_key}")

                    with LOCK:
                        PENDING_REQUESTS[target_key] = {
                            "source_group": reply_target,
                            "timestamp": time.time(),
                            "cmd": text
                        }

                    # ดีดคำสั่งเข้าปลายทาง B ทันที
                    try:
                        send_msg(GROUP_B_ID, text)
                        with LOCK:
                            METRICS["routed_a_to_b"] += 1
                        print(f"⚡ [ยิงจาก {chat_label} -> ปลายทาง B ({target_b_type}) สำเร็จ]: '{text}'")
                    except Exception as e:
                        print(f"❌ ยิงเข้าปลายทาง B ล้มเหลว: {e}")
                else:
                    print(f"ℹ️ [{chat_label}] มีสัญลักษณ์คำสั่ง ({', '.join(TRIGGER_SYMBOLS)}) แต่ไม่พบหมายเลขหรือพารามิเตอร์: '{text}'")

        except Exception as e:
            time.sleep(1.5)

threading.Thread(target=private_msg_loop, daemon=True).start()

while True:
    try:
        # ====================================================
        # 1. ตรวจสอบ "กลุ่ม A" (ถ้ามีการระบุ GROUP_A_ID ไว้ในคอนฟิก)
        # ====================================================
        recent_a = cl.getRecentMessagesV2(GROUP_A_ID, 15) or [] if GROUP_A_ID else []
        new_msgs_a = [m for m in recent_a if m.get(4) and m.get(4) not in SEEN_A]
        
        # จัดเรียงจากเก่าไปใหม่ เพื่อส่งตามลำดับที่พิมพ์จริง
        new_msgs_a.reverse()
        for msg in new_msgs_a:
            msg_id = msg.get(4)
            sender = msg.get(1) or ""
            SEEN_A.add(msg_id)
                
            text = extract_text(msg).strip()
            if not text:
                continue
                
            # ข้ามข้อความที่บอทเราเพิ่งดีดกลับมาตอบในกลุ่ม A
            with LOCK:
                if text in BOT_REPLIES_SENT:
                    BOT_REPLIES_SENT.discard(text)
                    continue
                
            print(f"🔔 [ข้อความใหม่ในกลุ่ม A] '{text}'")
            
            # 🛡️ เงื่อนไขสำคัญ: ข้อความต้องมีเครื่องหมาย # หรือ $ หรือ % เท่านั้น ถ้าไม่มีคือห้ามส่งเด็ดขาด
            TRIGGER_SYMBOLS = ['#', '$', '%']
            if not any(sym in text for sym in TRIGGER_SYMBOLS):
                # ข้อความทั่วไปที่ไม่มีสัญลักษณ์คำสั่ง (#, $, %) จะไม่ถูกส่งไปกลุ่ม B
                continue

            # 🛡️ [Access Control]: ตรวจสอบสิทธิ์ผู้ส่งในกลุ่ม A
            if ALLOWED_USERS and (sender not in ALLOWED_USERS and sender != my_mid):
                print(f"⛔ [กลุ่ม A] สกัดกั้นคำสั่งจากสมาชิกที่ไม่อยู่ใน Whitelist: {sender}")
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
                    with LOCK:
                        METRICS["routed_a_to_b"] += 1
                    print(f"⚡ [ยิงไปปลายทาง B ({target_b_type}) สำเร็จ]: '{text}'")
                except Exception as e:
                    print(f"❌ ยิงเข้าปลายทาง B ล้มเหลว: {e}")
            else:
                print(f"ℹ️ มีสัญลักษณ์คำสั่ง (#, $, %) แต่ไม่พบหมายเลขหรือพารามิเตอร์: '{text}' (ไม่ส่งไปปลายทาง B)")

        # ====================================================
        # 2. ตรวจสอบ "ปลายทาง B" (คำตอบจากบอท Master หรือ LINE OA)
        # ====================================================
        recent_b = cl.getRecentMessagesV2(GROUP_B_ID, 15) or []
        new_msgs_b = [m for m in recent_b if m.get(4) and m.get(4) not in SEEN_B]
        
        new_msgs_b.reverse()
        for msg in new_msgs_b:
            msg_id = msg.get(4)
            sender = msg.get(1) or ""
            SEEN_B.add(msg_id)
                
            # ถ้าเป็นข้อความที่ตัวเองส่งไปในปลายทาง B ให้ข้าม
            if sender == my_mid:
                continue
                
            text = extract_text(msg).strip()
            if not text:
                continue

            # 🛡️ [ป้องกันบั๊กคำสั่งคนอื่นในกลุ่ม B เด้งเข้ากลุ่ม A]
            # 1. ถ้าข้อความขึ้นต้นด้วยสัญลักษณ์คำสั่ง (#, $, %, /) ย่อมเป็นคำสั่งที่คนอื่นพิมพ์หาบอท ไม่ใช่คำตอบจากบอท
            if any(text.startswith(sym) for sym in ['#', '$', '%', '/']):
                if sender:
                    HUMAN_SENDERS_B.add(sender)
                print(f"ℹ️ [ข้ามคำสั่งของผู้ใช้อื่นในปลายทาง B]: จาก {sender}: '{text[:60]}'")
                continue

            # 3. ถ้ามีการระบุ MASTER_BOT_MIDS ผู้ส่งต้องเป็นบอท Master ในลิสต์เท่านั้น
            if MASTER_BOT_MIDS and sender not in MASTER_BOT_MIDS:
                continue

            print(f"🔔 [ข้อความใหม่ในปลายทาง B ({target_b_type})] จาก {sender}: '{text[:60]}...'")
            
            matched_target = None
            source_group = None
            clean_reply_digits = re.sub(r'\D', '', text)

            with LOCK:
                # 1. ตรวจสอบความตรงกันแบบเจาะจง (Exact Target / Digit Match)
                for target_key, data in list(PENDING_REQUESTS.items()):
                    if (target_key.lower() in text.lower()) or (target_key.isdigit() and len(target_key) >= 6 and target_key in clean_reply_digits):
                        matched_target = target_key
                        source_group = data["source_group"]
                        del PENDING_REQUESTS[target_key]
                        break

                # 2. กรณีคำสั่งกลุ่มช่วยเหลือ/เมนูคำสั่ง (help, menu, วิธีใช้, คำสั่ง, คู่มือ)
                if not matched_target:
                    help_keys = ['help', 'menu', 'วิธีใช้', 'คำสั่ง', 'คู่มือ', 'เช็ค']
                    is_help_reply = any(hk in text.lower() for hk in ['การใช้งาน', 'วิธีใช้', 'คำสั่ง', 'เมนู', 'help'])
                    for target_key, data in list(PENDING_REQUESTS.items()):
                        cmd_txt = data.get("cmd", "").lower()
                        is_help_cmd = target_key.lower() in help_keys or any(hk in cmd_txt for hk in help_keys)
                        # ต้องตรงกันทั้งคำสั่งต้นทางที่เป็น help และข้อความตอบกลับที่เป็นเนื้อหาช่วยเหลือ
                        if is_help_cmd and is_help_reply:
                            matched_target = target_key
                            source_group = data["source_group"]
                            del PENDING_REQUESTS[target_key]
                            break

                # 3. Fallback: หากในคิวมีคำสั่งรออยู่เพียง 1 รายการ (Single Pending Request FIFO)
                # เมื่อมีการส่งคำสั่งไป 1 ตัว และบอทปลายทางตอบข้อความกลับมาทันที ย่อมเป็นคำตอบของคำสั่งนั้นแน่นอน
                if not matched_target and len(PENDING_REQUESTS) == 1:
                    target_key, data = next(iter(PENDING_REQUESTS.items()))
                    if time.time() - data.get("timestamp", 0) <= TIMEOUT_SECONDS:
                        matched_target = target_key
                        source_group = data["source_group"]
                        del PENDING_REQUESTS[target_key]
                        
            if matched_target and source_group:
                print(f"🎯 [ปลายทาง B ({target_b_type}) ตอบกลับแล้ว!] พบข้อมูลตรงกับ Target: {matched_target}")
                try:
                    BOT_REPLIES_SENT.add(text)
                    sent_res = send_msg(source_group, text)
                    with LOCK:
                        METRICS["routed_b_to_dest"] += 1
                    if isinstance(sent_res, dict) and sent_res.get(4):
                        if str(source_group).startswith('u'):
                            SEEN_PRIVATE.add(sent_res.get(4))
                        else:
                            SEEN_A.add(sent_res.get(4))
                    dest_label = f"แชทส่วนตัว 1:1 ({source_group})" if str(source_group).startswith('u') else "กลุ่ม A"
                    print(f"🚀 [ดีดผลลัพธ์กลับไปยัง{dest_label} สำเร็จเรียบร้อย!]")
                except Exception as e:
                    dest_label = "แชทส่วนตัว 1:1" if str(source_group).startswith('u') else "กลุ่ม A"
                    print(f"❌ ส่งกลับ{dest_label} ล้มเหลว: {e}")

        # อัปเดตสถานะสำเร็จและรีเซ็ต consecutive_errors
        METRICS["last_poll_ts"] = time.time()
        METRICS["consecutive_errors"] = 0
        time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 หยุดการทำงานระบบ Personal LINE Bridge เรียบร้อยแล้ว")
        break
    except Exception as e:
        METRICS["consecutive_errors"] += 1
        err_wait = min(15.0, 1.0 * (1.5 ** (METRICS["consecutive_errors"] - 1)))
        print(f"❌ พบข้อผิดพลาดในลูปหลัก (ครั้งที่ {METRICS['consecutive_errors']}): {e} [หน่วงเวลา {err_wait:.1f}s]")
        time.sleep(err_wait)
