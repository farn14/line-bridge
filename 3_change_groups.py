# -*- coding: utf-8 -*-
"""
สคริปต์เลือก/อัปเดตกลุ่ม LINE และ LINE OA ด้วยตัวเองแบบอัตโนมัติ (Interactive Destination Selector)
รองรับทั้ง:
- กลุ่ม LINE (Group Chat: c...)
- บอท LINE Official Account (LINE OA / Contact: u...)
- หรือกรอก MID ปลายทางเองได้โดยตรง
"""
import os
import sys
import json
from CHRLINE import CHRLINE

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiI5ZDlhYTljYS1hMmVlLTRlZDktYjRmOC0wMTM1MzJhMWY0MmMiLCJhdWQiOiJMSU5FIiwiaWF0IjoxNzkxMzYyNTAzLCJleHAiOjE3OTE5NjczMDMsInNjcCI6IkxJTkVfQ09SRSIsInJ0aWQiOiI4ZWYzZmM4Ny0wYmNkLTRjNmItYTg1NS01YThjYzU0Mjk1YjkiLCJyZXhwIjoxODIyODk4NTAzLCJ2ZXIiOiIzLjAiLCJhaWQiOiJ1MmQ1ZjM4NTU4NjM2YmI2ZWZkOGEzZTI2MWZiZWQ4YWIiLCJsc2lkIjoiNGU0ZDFmODYtMmMxZC00Y2RhLWEyYmEtMTJjZTBhODNiYjA5IiwiZGlkIjoiTk9ORSIsImN0eXBlIjoiREVTS1RPUF9XSU4iLCJjbW9kZSI6IlNFQ09OREFSWSIsImNpZCI6IjAxMDAwMDAwMDAifQ.OUr_dfAteyhP_AsYeRqgVeOxmnElV4nfGj2WAyNWBRY'

# อ่าน Token จาก config.json ถ้ามี
saved_token = DEFAULT_TOKEN
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            c = json.load(f)
            saved_token = c.get("auth_token", DEFAULT_TOKEN)
    except Exception:
        pass

print("=" * 68)
print("🔍 กำลังดึงรายชื่อกลุ่ม LINE และ LINE OA จากบัญชีคน A...")
print("=" * 68)

try:
    cl = CHRLINE(authTokenOrEmail=saved_token, device="DESKTOPWIN", version="9.2.0.3421")
    
    # 1. ดึงกลุ่ม LINE
    mids_resp = cl.getAllChatMids()
    mids_raw = cl.checkAndGetValue(mids_resp, 1, 'memberChatMids') or (mids_resp.get(1, []) if isinstance(mids_resp, dict) else [])
    group_mids = [m for m in mids_raw if str(m).startswith('c')]
    
    groups = []
    if group_mids:
        chats_resp = cl.getChats(group_mids)
        chat_list = cl.checkAndGetValue(chats_resp, 1, 'chats') or (chats_resp.get(1, []) if isinstance(chats_resp, dict) else [])
        for idx, c in enumerate(chat_list, 1):
            mid = c.get(2) or group_mids[idx-1]
            name = c.get(6) or "ไม่มีชื่อกลุ่ม"
            groups.append({"id": mid, "name": name, "type": "GROUP"})

    # 2. ดึงรายชื่อเพื่อน / LINE OA
    contact_mids = cl.getAllContactIds() or []
    contacts = []
    if contact_mids:
        contacts_raw = cl.getContacts(contact_mids) or []
        for c in contacts_raw:
            c_mid = c.get(1)
            c_name = c.get(22) or c.get(2) or "ไม่ทราบชื่อ"
            contacts.append({"id": c_mid, "name": c_name, "type": "OA/USER"})

    # แสดงผลแยกหมวดหมู่
    all_destinations = []
    cur_no = 1
    
    print("\n👥 [หมวดที่ 1: กลุ่ม LINE ทั้งหมด]")
    print("-" * 68)
    if groups:
        for g in groups:
            all_destinations.append(g)
            print(f"  [{cur_no}] 👥 {g['name']}")
            print(f"       (Group MID: {g['id']})")
            cur_no += 1
    else:
        print("  (ไม่พบกลุ่มที่เข้าร่วม)")
    print("-" * 68)

    print("\n🤖 [หมวดที่ 2: LINE Official Account / เพื่อน]")
    print("-" * 68)
    if contacts:
        for c in contacts:
            all_destinations.append(c)
            print(f"  [{cur_no}] 🤖 {c['name']}")
            print(f"       (User/OA MID: {c['id']})")
            cur_no += 1
    else:
        print("  (ไม่พบเพื่อนหรือ LINE OA)")
    print("-" * 68)

    print("\n👉 กรุณาเลือกต้นทางและปลายทาง:")
    
    # 1. เลือกต้นทาง (กลุ่ม A ที่ผู้ใช้พิมพ์คำสั่ง)
    sel_a = None
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

    # 2. เลือกปลายทาง B (กลุ่ม B หรือ LINE OA สำหรับยิงไปคิวรี)
    sel_b = None
    print("\n💡 สำหรับ 'ปลายทาง B': สามารถใส่ 'หมายเลขในรายการ' หรือ 'พิมพ์ MID ตรงๆ' (เช่น u... หรือ c...) ได้ครับ")
    while True:
        val_b = input(f"2️⃣ เลือกหมายเลข หรือใส่ MID สำหรับ 'ปลายทาง B' (กลุ่ม หรือ LINE OA): ").strip()
        if not val_b:
            continue
            
        # ถ้าเป็นตัวเลขในรายการ
        if val_b.isdigit():
            num_b = int(val_b)
            if 1 <= num_b <= len(all_destinations):
                sel_b = all_destinations[num_b - 1]
                break
            print(f"⚠️ กรุณาเลือกหมายเลขระหว่าง 1 ถึง {len(all_destinations)}")
        # ถ้าผู้ใช้พิมพ์ MID เข้ามาตรงๆ
        elif val_b.startswith("u") or val_b.startswith("c"):
            sel_b = {
                "id": val_b,
                "name": "Custom LINE OA / Destination",
                "type": "OA/USER" if val_b.startswith("u") else "GROUP"
            }
            break
        else:
            print("⚠️ กรุณาระบุเป็นหมายเลขในรายการ หรือ MID ที่ขึ้นต้นด้วย u หรือ c ครับ")

    # บันทึกการตั้งค่าลง config.json
    config_data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            pass

    config_data.update({
        "group_a_id": sel_a["id"],
        "group_a_name": sel_a["name"],
        "group_b_id": sel_b["id"],
        "group_b_name": sel_b["name"],
        "group_b_type": sel_b["type"],
        "timeout_seconds": config_data.get("timeout_seconds", 90)
    })
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
        
    print("\n" + "=" * 68)
    print("✅ บันทึกปลายทางใหม่เรียบร้อย 100%!")
    print(f"📍 ต้นทาง A : {sel_a['name']} ({sel_a['id']}) [{sel_a['type']}]")
    print(f"📍 ปลายทาง B: {sel_b['name']} ({sel_b['id']}) [{sel_b['type']}]")
    print(f"⏱️ Timeout   : {config_data['timeout_seconds']} วินาที (1.30 นาที)")
    print("=" * 68)
    print("💡 สามารถดับเบิลคลิก '2_RUN_BRIDGE.bat' เพื่อเริ่มทำงานได้ทันทีครับ!")
    
except Exception as e:
    print(f"\n❌ เกิดข้อผิดพลาด: {e}")

input("\nกด Enter เพื่อปิดหน้าต่างนี้...")
