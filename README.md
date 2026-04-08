# ShopBack 回饋率追蹤器

自動爬取 ShopBack 台灣各旅遊平台的回饋率，每天兩次，歷史資料存在 `data/cashback_history.json`。

## 追蹤平台
- Hotels.com
- Booking.com
- KKday
- Trip.com
- Agoda
- Klook

## 快速開始

### 1. Fork 這個 repo 到你的 GitHub

### 2. 本機測試（可選）

```bash
# 安裝依賴
pip install -r requirements.txt
playwright install chromium

# 執行爬蟲
python scraper/shopback_scraper.py
```

### 3. 啟用 GitHub Actions

Fork 後進入你的 repo → **Actions** → 點選 **I understand my workflows, go ahead and enable them**

自動排程：每天 **09:00** 和 **21:00**（台灣時間）執行。

手動觸發：**Actions → ShopBack 回饋率定時爬蟲 → Run workflow**

### 4. 連接儀表板

將儀表板的 JSON 來源 URL 設定為你的 repo raw 連結：

```
https://raw.githubusercontent.com/你的帳號/shopback-tracker/main/data/cashback_history.json
```

## 資料格式

```json
[
  {
    "platform": "Hotels.com",
    "rate": 8.5,
    "is_upsized": true,
    "url": "https://www.shopback.com.tw/hotels-com",
    "date": "2026-04-08",
    "scraped_at": "2026-04-08 09:00:15"
  }
]
```

## 如果 selector 壞掉了？

ShopBack 改版時 selector 可能失效。
打開 `scraper/shopback_scraper.py`，更新 `selectors` 列表中的 CSS selector。
用瀏覽器開發者工具（F12）找到回饋率數字的 HTML 元素即可。

## 費用

**完全免費。** GitHub Actions 免費方案每月 2,000 分鐘，本爬蟲每次約 2-3 分鐘，
一天兩次 = 每月約 150 分鐘，遠低於上限。
