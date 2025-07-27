from flask import Flask, request, Response, jsonify
import requests
import asyncio
import httpx
import threading
import time
import urllib3
import os
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

PORT = int(os.environ.get('PORT', 8398))
SELF_URL = os.environ.get("SELF_URL", f"http://127.0.0.1:{PORT}")

JWT_CACHE = {}
ACCS_FILE = "accs.txt"

# تحميل الحسابات من ملف accs.txt
def load_accounts():
    if not os.path.exists(ACCS_FILE):
        print(f"[ERROR] {ACCS_FILE} not found!")
        return {}
    try:
        with open(ACCS_FILE, "r") as f:
            data = json.load(f)
            print(f"[INFO] Loaded {len(data)} accounts from {ACCS_FILE}")
            return data
    except Exception as e:
        print(f"[ERROR] Failed to load {ACCS_FILE}: {e}")
        return {}

# الحصول على JWT لكل حساب
def get_jwt(uid, password):
    url = f"https://jwt-gen-api-v2.onrender.com/token?uid={uid}&password={password}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if "token" in data:
                return data["token"]
        print(f"[JWT-ERROR] {uid}: {response.text}")
        return None
    except Exception as e:
        print(f"[JWT-EXCEPTION] {uid}: {e}")
        return None

# دالة غير متزامنة لإرسال طلب الصداقة
async def async_add_fr(player_id, token):
    try:
        proxy_url = f"https://panel-friend-bot.vercel.app/request?token={token}&uid={player_id}"
        async with httpx.AsyncClient(timeout=60, verify=False) as client:
            response = await client.get(proxy_url)
            return f"{player_id} -> HTTP {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return f"Error for {player_id}: {e}"

# ثريد لتحديث التوكنات كل ساعة من ملف الحسابات
def refresh_tokens_background():
    while True:
        print("[DEBUG] Refreshing all JWT tokens...")
        accounts = load_accounts()
        for uid, pw in accounts.items():
            token = get_jwt(uid, pw)
            if token:
                JWT_CACHE[uid] = token
                print(f"[JWT] {uid} -> Token OK")
            else:
                print(f"[JWT] {uid} -> Failed")
        time.sleep(3600)

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200

# مولد نتائج ارسال طلب الصداقة
def generate(player_id):
    yield f"📨 Sending friend requests to player {player_id}...\n\n"
    for uid in JWT_CACHE:
        token = JWT_CACHE.get(uid)
        if not token:
            yield f"❌ No JWT for {uid}\n"
            continue
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(async_add_fr(player_id, token))
        yield f"{uid} ➤ {result}\n"

@app.route("/spam")
def spam():
    player_id = request.args.get("id")
    if not player_id:
        return "Please provide ?id=UID"
    return Response(generate(player_id), content_type="text/plain")

if __name__ == "__main__":
    threading.Thread(target=refresh_tokens_background, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)