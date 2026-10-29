import time
import requests

BASE = "http://127.0.0.1:8000/api"
LOGIN = {"username": "carol", "password": "123456"}

r = requests.post(BASE + "/auth/login", json=LOGIN).json()
token = r["data"]["token"]
h = {"Authorization": f"Bearer {token}"}


def test(model_key: str, prompt: str):
    r = requests.post(
        BASE + "/conversations",
        headers=h,
        json={"title": f"test-{model_key}", "model_key": model_key},
    ).json()
    cid = r["data"]["id"]
    t = time.time()
    r = requests.post(
        BASE + f"/conversations/{cid}/messages",
        headers=h,
        json={"content": prompt},
        timeout=120,
    )
    elapsed = time.time() - t
    data = r.json()
    print(f"[{model_key}] elapsed={elapsed:.2f}s code={data.get('code')}")
    if data.get("data"):
        print(f"  reply: {data['data']['assistant_message']['content']}")
    else:
        print(f"  error: {data}")


test("local:pretrain-v2", "人工智能")
test("local:sft-v2", "你是谁")
test("local:lora-v2-wukong", "你是谁")
test("local:lora-v2-wukong", "你的师父是谁")
