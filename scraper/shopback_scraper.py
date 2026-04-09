"""
ShopBack 回饋率爬蟲
爬取 Hotels.com、Booking.com、KKday、Trip.com 等平台的回饋率
並儲存歷史記錄到 data/cashback_history.json
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# ── 設定 ──────────────────────────────────────────────
TARGETS = {
    "Hotels.com":  "https://www.shopback.com.tw/hotels-com",
    "Booking.com": "https://www.shopback.com.tw/booking-com",
    "KKday":       "https://www.shopback.com.tw/kkday",
    "Trip.com":    "https://www.shopback.com.tw/trip-com",
    "Agoda":       "https://www.shopback.com.tw/agoda",
    "Klook":       "https://www.shopback.com.tw/klook",
}

DATA_FILE = Path(__file__).parent.parent / "data" / "cashback_history.json"


# ── 爬蟲核心 ──────────────────────────────────────────
def scrape_cashback_rate(page, platform: str, url: str) -> dict | None:
    """爬取單一平台的回饋率"""
    try:
        print(f"  -> 爬取 {platform}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # ShopBack 用 MUI + JS 渲染，等待較長時間確保展開
        page.wait_for_timeout(5000)

        rate_text = None

        # 策略 1：找所有 font_bold 的 <p>，取出包含 % 的文字
        try:
            els = page.locator("p.font_bold").all()
            for el in els:
                txt = el.inner_text(timeout=2000).strip()
                if "%" in txt and re.search(r'\d', txt):
                    rate_text = txt
                    print(f"    策略1 找到: {txt}")
                    break
        except Exception:
            pass

        # 策略 2：找 class 含 font_bold 的 <p>
        if not rate_text:
            try:
                els = page.locator("p[class*='font_bold']").all()
                for el in els:
                    txt = el.inner_text(timeout=2000).strip()
                    if re.search(r'\d+.*%', txt):
                        rate_text = txt
                        print(f"    策略2 找到: {txt}")
                        break
            except Exception:
                pass

        # 策略 3：展開 Accordion 後再找
        if not rate_text:
            try:
                accordions = page.locator(".MuiAccordion-root").all()
                for acc in accordions[:3]:
                    try:
                        acc.click(timeout=2000)
                        page.wait_for_timeout(800)
                    except Exception:
                        pass
                els = page.locator("p.font_bold").all()
                for el in els:
                    txt = el.inner_text(timeout=2000).strip()
                    if "%" in txt and re.search(r'\d', txt):
                        rate_text = txt
                        print(f"    策略3 找到: {txt}")
                        break
            except Exception:
                pass

        # 策略 4：從整個頁面 HTML 用 regex 找
        if not rate_text:
            content = page.content()
            match = re.search(
                r'font_bold[^>]*>([^<]*\d+(?:\.\d+)?%[^<]*)<',
                content
            )
            if match:
                rate_text = match.group(1)
                print(f"    策略4 找到: {rate_text}")
            else:
                match = re.search(
                    r'(\d+(?:\.\d+)?)\s*%\s*(?:Cashback|回饋|cashback|現金回饋)',
                    content,
                    re.IGNORECASE
                )
                if match:
                    rate_text = match.group(0)
                    print(f"    策略4b 找到: {rate_text}")

        if not rate_text:
            print(f"    WARNING: 找不到 {platform} 的回饋率")
            return None

        # 抽出數字
        numbers = re.findall(r'\d+(?:\.\d+)?', rate_text)
        if not numbers:
            return None

        # 取最大的那個（有時會顯示「最高 X%」）
        rate = max(float(n) for n in numbers)

        # 判斷是否為 upsized（特促）
        is_upsized = bool(re.search(r'upsized|特促|加碼', page.content(), re.IGNORECASE))

        return {
            "platform": platform,
            "rate": rate,
            "is_upsized": is_upsized,
            "url": url,
        }

    except Exception as e:
        print(f"    ERROR: {platform} 發生錯誤：{e}")
        return None


def run_scraper():
    """執行爬蟲，抓取所有平台"""
    results = []
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n開始爬取 ShopBack 回饋率 [{now}]\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="zh-TW",
        )
        page = context.new_page()

        for platform, url in TARGETS.items():
            result = scrape_cashback_rate(page, platform, url)
            if result:
                result["date"] = today
                result["scraped_at"] = now
                results.append(result)
                print(f"    OK {platform}: {result['rate']}%"
                      + (" (加碼中)" if result["is_upsized"] else ""))

        browser.close()

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
    today = datetime.now().strftime("%Y-%m-%d")
    history = [r for r in history if r.get("date") != today]
    history.extend(new_results)
    history.sort(key=lambda x: x.get("scraped_at", ""))
    return history


def print_summary(history: list):
    platforms = list(TARGETS.keys())
    print("\n" + "-" * 50)
    print("各平台回饋率摘要")
    print("-" * 50)
    for platform in platforms:
        records = [r for r in history if r["platform"] == platform]
        if not records:
            continue
        latest = records[-1]
        rates = [r["rate"] for r in records]
        max_rate = max(rates)
        is_max = latest["rate"] == max_rate and len(records) > 1
        flag = " *** 歷史最高！" if is_max else ""
        upsized = " (加碼)" if latest.get("is_upsized") else ""
        print(f"  {platform:15s}  {latest['rate']:5.1f}%{upsized}  (歷史最高 {max_rate:.1f}%){flag}")
    print("-" * 50 + "\n")


# ── 主程式 ────────────────────────────────────────────
if __name__ == "__main__":
    new_results = run_scraper()

    if new_results:
        history = load_history()
        history = merge_results(history, new_results)
        save_history(history)
        print(f"\n已儲存 {len(new_results)} 筆記錄 -> {DATA_FILE}")
        print_summary(history)
    else:
        print("\nWARNING: 本次沒有抓到任何資料，請檢查網路或 selector 是否需要更新")
