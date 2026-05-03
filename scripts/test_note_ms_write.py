import time
import httpx

API = "https://paste.rs/"


def main() -> int:
    test_text = (
        f"FeishuAutoRepair paste.rs connectivity test\n"
        f"time={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    print("[1/2] POST to paste.rs")
    resp = httpx.post(
        API,
        content=test_text.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        timeout=30,
    )
    print(f"status={resp.status_code}")
    print(f"body={resp.text}")
    if resp.status_code != 201:
        print("write failed")
        return 1

    paste_url = resp.text.strip()
    print(f"[2/2] GET {paste_url}")
    resp2 = httpx.get(paste_url, timeout=15)
    print(f"status={resp2.status_code}")
    if resp2.status_code == 200 and resp2.text == test_text:
        print("result=ok")
        print(f"url={paste_url}")
        return 0

    print("result=mismatch or read failed")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
