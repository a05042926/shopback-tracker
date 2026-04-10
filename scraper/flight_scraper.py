import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 要追蹤的航線
ROUTES = [
    {"from": "TPE", "to": "NRT", "label": "台北桃園 → 東京成田"},
    {"from": "TPE", "to": "CTS", "label": "台北桃園 → 北海道札幌"},
    {"from": "TPE", "to": "SEA", "label": "台北桃園 → 西雅圖"},
]

def search_flights(origin, destination, date_str):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": date_str,
        "currency": "TWD",
        "hl": "zh-tw",
        "api_key": SERPAPI_KEY,
        "type": "2",  # 單程
    }
    response = requests.get(url, params=params)
    data = response.json()

    best_flights = data.get("best_flights", []) + data.get("other_flights", [])
    if not best_flights:
        return None

    prices = []
    for flight in best_flights:
        price = flight.get("price")
        if price:
            prices.append(price)

    return min(prices) if prices else None

def main():
    # 查 30 天後的票價（避免太近沒票）
    target_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    data_path = Path("data/flight_history.json")
    if data_path.exists():
        with open(data_path) as f:
            history = json.load(f)
    else:
        history = {}

    for route in ROUTES:
        key = f"{route['from']}-{route['to']}"
        price = search_flights(route["from"], route["to"], target_date)
        print(f"{route['label']}: {price} TWD")

        if key not in history:
            history[key] = {"label": route["label"], "records": []}

        if price:
            history[key]["records"].append({
                "timestamp": timestamp,
                "date": target_date,
                "price": price
            })

    data_path.parent.mkdir(exist_ok=True)
    with open(data_path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print("Done! 資料已存至 data/flight_history.json")

if __name__ == "__main__":
    main()
