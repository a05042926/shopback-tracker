"""
航班價格爬蟲
使用 Google Flights 頁面抓取特定航線票價
並儲存到 data/flight_history.json

設定方式：
  1. 編輯下方 ROUTES 清單，填入你想追蹤的航線
  2. 在 GitHub repo Settings → Secrets 加入：
     SERPAPI_KEY = 你的 SerpAPI key（免費方案每月 100 次）
     若不想用 SerpAPI，設定 USE_SERPAPI = False 改用直接爬蟲
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request

# ── 設定 ─────────────────────────────────────────────
ROUTES = [
    # { "from": "出發機場代碼", "to": "目的機場代碼", "label": "顯示名稱" }
    {"from": "TPE", "to": "NRT", "label": "台北→東京"},
    {"from": "TPE", "to": "OSA", "label": "台北→大阪"},
    {"from": "TPE", "to": "HKG", "label": "台北→香港"},
    # 可自行新增更多航線
]

# 查詢未來幾天的票價（從明天開始往後 N 天）
DAYS_AHEAD = 30

# SerpAPI key（從環境變數讀，在 GitHub Secrets 設定）
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
USE_SERPAPI = bool(SERPAPI_KEY)

DATA_FILE = Path(__file__).parent.parent / "data" / "flight_history.json"


# ── SerpAPI 方式（推薦，較穩定）──────────────────────
def fetch_via_serpapi(route: dict, date_str: str) -> dict | None:
    """用 SerpAPI 查 Google Flights 票價"""
    params = {
        "engine": "google_flights",
        "departure_id": route["from"],
        "arrival_id": route["to"],
        "outbound_date": date_str,
        "currency": "TWD",
        "hl": "zh-TW",
        "api_key": SERPAPI_KEY,
        "type": "2",  # 單程
    }
    url = "https://serpapi.com/search.json?" + urlencode(params)
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        best = data.get("best_flights", []) or data.get("other_flights", [])
        if not best:
            return None

        prices = []
        airlines_seen = []
        for flight_group in best[:5]:
            price = flight_group.get("price")
            if price:
                prices.append(price)
            for leg in flight_group.get("flights", []):
                airline = leg.get("airline", "")
                if airline and airline not in airlines_seen:
                    airlines_seen.append(airline)

        if not prices:
            return None

        return {
            "min_price": min(prices),
            "airlines": airlines_seen[:3],
            "source": "serpapi",
        }

    except Exception as e:
        print(f"    SerpAPI 錯誤：{e}")
        return None


# ── 直接爬 Google Flights（備用，較不穩定）──────────
def fetch_direct(route: dict, date_str: str) -> dict | None:
    """直接爬 Google Flights（JS 渲染，可能不穩定）"""
    try:
        from playwright.sync_api import sync_playwright

        url = (
            f"https://www.google.com/travel/flights/search"
            f"?tfs=CBwQAhopagwIAxIIL20vMGozamcSCjIwMjUtMTEtMDFyDQgDEgkvbS8wNHJtMHAB"
        )
        # 直接組更簡單的 URL
        url = (
            f"https://www.google.com/travel/flights?"
            f"q=Flights+from+{route['from']}+to+{route['to']}+on+{date_str}"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 找票價
            prices = []
            price_els = page.locator("[data-gs]").all()
            for el in price_els[:10]:
                text = el.inner_text()
                match = re.search(r'[\$NT\$]?\s*(\d[\d,]+)', text)
                if match:
                    price = int(match.group(1).replace(',', ''))
                    if 1000 < price < 500000:  # 合理票價範圍
                        prices.append(price)

            browser.close()

        return {"min_price": min(prices), "airlines": [], "source": "direct"} if prices else None

    except Exception as e:
        print(f"    直接爬蟲錯誤：{e}")
        return None


# ── 主爬蟲 ───────────────────────────────────────────
def run_flight_scraper():
    results = []
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    today_str = now.strftime("%Y-%m-%d")

    print(f"\n✈️  開始爬取航班價格 [{now_str}]\n")
    print(f"  方式：{'SerpAPI' if USE_SERPAPI else '直接爬蟲'}\n")

    # 選取查詢日期：明天、7天後、14天後、30天後
    target_dates = []
    for days in [1, 7, 14, 30]:
        if days <= DAYS_AHEAD:
            d = (now + timedelta(days=days)).strftime("%Y-%m-%d")
            target_dates.append(d)

    for route in ROUTES:
        print(f"  ✈️  {route['label']} ({route['from']}→{route['to']})")

        for dep_date in target_dates:
            print(f"     出發日 {dep_date}...", end=" ")

            if USE_SERPAPI:
                result = fetch_via_serpapi(route, dep_date)
            else:
                result = fetch_direct(route, dep_date)

            if result:
                record = {
                    "route": f"{route['from']}-{route['to']}",
                    "label": route["label"],
                    "departure_date": dep_date,
                    "check_date": today_str,
                    "checked_at": now_str,
                    "min_price_twd": result["min_price"],
                    "airlines": result["airlines"],
                    "source": result["source"],
                }
                results.append(record)
                print(f"NT${result['min_price']:,}")
            else:
                print("找不到票價")

            time.sleep(1.5)  # 避免請求太頻繁

    return results


# ── 資料儲存 ──────────────────────────────────────────
def load_history() -> list:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history: list):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def merge_results(history: list, new_results: list) -> list:
    """同一天 + 同航線 + 同出發日，只保留最新一筆"""
    today = datetime.now().strftime("%Y-%m-%d")
    history = [
        r for r in history
        if not (r.get("check_date") == today
                and r.get("route") in [x["route"] for x in new_results]
                and r.get("departure_date") in [x["departure_date"] for x in new_results])
    ]
    history.extend(new_results)
    history.sort(key=lambda x: x.get("checked_at", ""))
    return history


def print_summary(new_results: list):
    if not new_results:
        return
    print("\n" + "─" * 55)
    print("✈️  航班價格摘要（本次爬取）")
    print("─" * 55)
    routes = list({r["route"] for r in new_results})
    for route in routes:
        recs = [r for r in new_results if r["route"] == route]
        label = recs[0]["label"]
        print(f"\n  {label}")
        for r in sorted(recs, key=lambda x: x["departure_date"]):
            print(f"    {r['departure_date']}  NT${r['min_price_twd']:>8,}")
    print("─" * 55 + "\n")


# ── 主程式 ────────────────────────────────────────────
if __name__ == "__main__":
    if not USE_SERPAPI:
        print("⚠️  未設定 SERPAPI_KEY，改用直接爬蟲（穩定性較低）")
        print("   建議：到 https://serpapi.com 免費註冊，取得 API key\n")

    new_results = run_flight_scraper()

    if new_results:
        history = load_history()
        history = merge_results(history, new_results)
        save_history(history)
        print(f"\n💾 已儲存 {len(new_results)} 筆記錄 → {DATA_FILE}")
        print_summary(new_results)
    else:
        print("\n⚠️  本次沒有抓到任何資料")
