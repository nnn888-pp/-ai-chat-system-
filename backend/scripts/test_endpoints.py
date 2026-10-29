import time
import requests

BASE = "http://127.0.0.1:8000/api"

r = requests.post(BASE + "/auth/login", json={"username": "carol", "password": "123456"}).json()
token = r["data"]["token"]
h = {"Authorization": f"Bearer {token}"}

r = requests.get(BASE + "/models", headers=h).json()
print("models:")
for m in r["data"]["list"]:
    print(f"  {m['kind']} | {m['status']:8s} | {m['key']} | {m.get('error_msg','')}")

r = requests.get(BASE + "/conversations", headers=h).json()
cid = r["data"]["list"][0]["id"]
print("cid =", cid)

print("== send ==")
t = time.time()
try:
    r = requests.post(
        BASE + f"/conversations/{cid}/messages",
        headers=h,
        json={"content": "你是谁"},
        timeout=120,
    )
    print("http", r.status_code, "elapsed", round(time.time() - t, 2))
    data = r.json()
    print("code", data.get("code"), "msg", data.get("message"))
    if data.get("data"):
        print("reply raw:", repr(data["data"]["assistant_message"]["content"]))
        print("reply utf8 bytes:", data["data"]["assistant_message"]["content"].encode("utf-8"))
        print("model_key:", data["data"]["assistant_message"]["model_key"])
except Exception as e:
    print("elapsed", round(time.time() - t, 2))
    print("ERROR", e)
