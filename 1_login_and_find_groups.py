# -*- coding: utf-8 -*-
"""
สคริปต์ขั้นตอนที่ 1: ล็อกอินบัญชี 'คน A' ใหม่ ผ่าน LINE PC Official Protocol (9.2.0 ล่าสุด)
พร้อมสแกน QR Code, บันทึก Token, ดึงกลุ่ม และบันทึกลง config.json อัตโนมัติ
"""
import os
import sys
import time
import json
import shutil
import threading
from CHRLINE import CHRLINE

SESSION_DIR = os.path.join(os.path.dirname(__file__), "session_data")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

print("=" * 65)
print("🚀 กำลังเริ่มระบบล็อกอินบัญชี LINE ใหม่สำหรับ 'คน A' (Personal LINE Bridge)...")
print("=" * 65)

# ล้างแคชเซสชันเก่าเพื่อให้ได้ QR Code ใหม่แน่นอน
if os.path.exists(SESSION_DIR):
    try:
        shutil.rmtree(SESSION_DIR, ignore_errors=True)
    except Exception:
        pass

# เธรดตรวจจับรูปภาพ QR Code เพื่อเปิดบนหน้าจอให้อัตโนมัติ
def qr_watcher():
    img_dir = os.path.join(SESSION_DIR, ".images")
    opened = set()
    for _ in range(60):
        time.sleep(0.5)
        if os.path.exists(img_dir):
            try:
                for f in os.listdir(img_dir):
                    if f.endswith(".png") and f not in opened:
                        opened.add(f)
                        full_p = os.path.join(img_dir, f)
                        print(f"\n🖼️ กำลังเปิดรูปภาพ QR Code บนหน้าจอของคุณอัตโนมัติ: {f}")
                        os.startfile(full_p)
                        return
            except Exception:
                pass

threading.Thread(target=qr_watcher, daemon=True).start()

try:
    print("\n⏳ กำลังสร้าง QR Code ใหม่ กรุณารอสักครู่...")
    cl = CHRLINE(device="DESKTOPWIN", version="9.2.0.3421", savePath=SESSION_DIR)
    
    # ดึงโปรไฟล์
    profile = cl.getProfile()
    display_name = cl.checkAndGetValue(profile, 20, 'displayName') or "ผู้ใช้ LINE"
    mid = cl.checkAndGetValue(profile, 1, 'mid') or getattr(cl, 'mid', '') or ""
    new_token = cl.authToken
    
    # ดึงกุญแจ E2EE ของบัญชีใหม่
    e2ee_keys = cl.getE2EESelfKeyData(mid) or {}
    
    print("\n" + "=" * 65)
    print("🎉 เข้าสู่ระบบบัญชี LINE ใหม่สำเร็จ 100%!")
    print(f"👤 บัญชีคน A: {display_name}")
    print(f"🔑 บัญชี MID: {mid}")
    print("=" * 65)
    
    # ดึงทั้งกลุ่ม LINE และ LINE OA / เพื่อน
    print("\n🔍 กำลังค้นหารายชื่อกลุ่ม LINE และ LINE OA ทั้งหมดของคุณ กรุณารอสักครู่...\n")
    
    # 1. กลุ่ม LINE
    mids_resp = cl.getAllChatMids()
    mids_raw = cl.checkAndGetValue(mids_resp, 1, 'memberChatMids') or (mids_resp.get(1, []) if isinstance(mids_resp, dict) else [])
    group_mids = [m for m in mids_raw if str(m).startswith('c')]
    
    groups = []
    if group_mids:
        chats_resp = cl.getChats(group_mids)
        chat_list = cl.checkAndGetValue(chats_resp, 1, 'chats') or (chats_resp.get(1, []) if isinstance(chats_resp, dict) else [])
        for idx, c in enumerate(chat_list, 1):
            g_mid = c.get(2) or group_mids[idx-1]
            g_name = c.get(6) or "ไม่มีชื่อกลุ่ม"
            groups.append({"id": g_mid, "name": g_name, "type": "GROUP"})

    # 2. รายชื่อเพื่อน / LINE OA
    contact_mids = cl.getAllContactIds() or []
    contacts = []
    if contact_mids:
        contacts_raw = cl.getContacts(contact_mids) or []
        for c in contacts_raw:
            c_mid = c.get(1)
            c_name = c.get(22) or c.get(2) or "ไม่ทราบชื่อ"
            contacts.append({"id": c_mid, "name": c_name, "type": "OA/USER"})

    all_destinations = []
    cur_no = 1
    
    print("👥 [หมวดที่ 1: กลุ่ม LINE ทั้งหมด]")
    print("-" * 65)
    if groups:
        for g in groups:
            all_destinations.append(g)
            print(f"  [{cur_no}] 👥 {g['name']}")
            print(f"       (Group ID: {g['id']})")
            cur_no += 1
    else:
        print("  (ไม่พบกลุ่มที่เข้าร่วม)")
    print("-" * 65)

    print("\n🤖 [หมวดที่ 2: LINE Official Account / เพื่อน]")
    print("-" * 65)
    if contacts:
        for c in contacts:
            all_destinations.append(c)
            print(f"  [{cur_no}] 🤖 {c['name']}")
            print(f"       (OA/User MID: {c['id']})")
            cur_no += 1
    else:
        print("  (ไม่พบเพื่อนหรือ LINE OA)")
    print("-" * 65)

    sel_a = None
    sel_b = None

    if all_destinations:
        print("\n👉 กรุณาเลือกต้นทางและปลายทาง:")
        while True:
            try:
                val_a = input(f"1️⃣ เลือกหมายเลขสำหรับ 'ต้นทางกลุ่ม A' (กลุ่มที่ส่งคำสั่ง): ").strip()
                num_a = int(val_a)
                if 1 <= num_a <= len(all_destinations):
                    sel_a = all_destinations[num_a - 1]
                    break
                print(f"⚠️ กรุณาเลือกหมายเลขระหว่าง 1 ถึง {len(all_destinations)}")
            except ValueError:
                print("⚠️ กรุณาใส่เป็นตัวเลขครับ")

        print("\n💡 สำหรับ 'ปลายทาง B': สามารถใส่ 'หมายเลขในรายการ' หรือ 'พิมพ์ MID ตรงๆ' (เช่น u... หรือ c...) ได้ครับ")
        while True:
            val_b = input(f"2️⃣ เลือกหมายเลข หรือใส่ MID สำหรับ 'ปลายทาง B' (กลุ่ม หรือ LINE OA): ").strip()
            if not val_b:
                continue
            if val_b.isdigit():
                num_b = int(val_b)
                if 1 <= num_b <= len(all_destinations):
                    sel_b = all_destinations[num_b - 1]
                    break
                print(f"⚠️ กรุณาเลือกหมายเลขระหว่าง 1 ถึง {len(all_destinations)}")
            elif val_b.startswith("u") or val_b.startswith("c"):
                sel_b = {
                    "id": val_b,
                    "name": "Custom Destination",
                    "type": "OA/USER" if val_b.startswith("u") else "GROUP"
                }
                break
            else:
                print("⚠️ กรุณาระบุเป็นหมายเลขในรายการ หรือ MID ที่ขึ้นต้นด้วย u หรือ c ครับ")
    else:
        print("\n⚠️ ไม่พบกลุ่มหรือผู้ติดต่อในบัญชี LINE")
        val_a = input("กรุณาระบุ MID กลุ่มต้นทาง A (ขึ้นต้นด้วย c...): ").strip()
        val_b = input("กรุณาระบุ MID ปลายทาง B (ขึ้นต้นด้วย c... หรือ u...): ").strip()
        sel_a = {"id": val_a, "name": "กลุ่มต้นทาง A", "type": "GROUP"}
        sel_b = {"id": val_b, "name": "ปลายทาง B", "type": "OA/USER" if val_b.startswith("u") else "GROUP"}

    # บันทึกทุกอย่างลง config.json อัตโนมัติ
    new_config = {
        "auth_token": new_token,
        "mid": mid,
        "display_name": display_name,
        "e2ee_keys": e2ee_keys,
        "group_a_id": sel_a["id"],
        "group_a_name": sel_a["name"],
        "group_b_id": sel_b["id"],
        "group_b_name": sel_b["name"],
        "group_b_type": sel_b.get("type", "GROUP"),
        "timeout_seconds": 90
    }
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, ensure_ascii=False, indent=2)
        
    print("\n" + "=" * 65)
    print("💾 บันทึก Token, กุญแจ E2EE และข้อมูลกลุ่ม/LINE OA ใหม่ลง config.json เรียบร้อยแล้ว!")
    print(f"📍 ต้นทาง A : {sel_a['name']} ({sel_a['id']})")
    print(f"📍 ปลายทาง B ({sel_b.get('type', 'GROUP')}): {sel_b['name']} ({sel_b['id']})")
    print("=" * 65)
    print("💡 ทุกอย่างพร้อมแล้ว! สามารถดับเบิลคลิก '2_RUN_BRIDGE.bat' เพื่อเริ่มทำงานได้ทันทีครับ!")

except Exception as e:
    print(f"\n❌ เกิดข้อผิดพลาด: {e}")

input("\nกด Enter เพื่อปิดหน้าต่างนี้...")
