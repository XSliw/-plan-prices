#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер цен: Wildberries API + Куфар API + Lamoda.
Запускается по расписанию GitHub Actions.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

# data.py лежит на уровень выше
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import data

MAX_PER_SOURCE = 3
OUT_FILE = os.path.join(os.path.dirname(__file__), "..", "prices.json")

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "application/json, text/html, */*",
}


def get(url, **kw):
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=14, **kw)
        r.raise_for_status()
        return r
    except Exception:
        return None


# -------- Wildberries --------
def wb_search(query):
    results = []
    url = (
        "https://search.wb.ru/exactmatch/ru/common/v4/search"
        "?appType=1&curr=byn&dest=-59202"
        "&query=" + quote(query) +
        "&resultset=catalog&sort=priceup&suppressSpellcheck=false"
    )
    r = get(url)
    if not r:
        return []
    for it in r.json().get("data", {}).get("products", [])[:MAX_PER_SOURCE * 2]:
        raw = it.get("salePriceU") or it.get("priceU")
        if not raw:
            continue
        price = round(raw / 100, 2)
        nm_id = it.get("id", "")
        name = (it.get("name") or query)[:80]
        link = "https://www.wildberries.by/catalog/" + str(nm_id) + "/detail.aspx"
        results.append({"source": "Wildberries", "name": name, "price": price, "url": link})
    results.sort(key=lambda x: x["price"])
    return results[:MAX_PER_SOURCE]


# -------- Куфар --------
def kufar_search(query):
    results = []
    url = (
        "https://api.kufar.by/search-api/v2/search/rendered-paginated"
        "?lang=ru&query=" + quote(query) + "&size=8&sort=price_asc"
    )
    r = get(url)
    if not r:
        return []
    for ad in r.json().get("ads", []):
        params = {p["pu"]: p["vl"] for p in ad.get("ad_parameters", [])}
        raw = params.get("price") or str(ad.get("price_byn", "") or "")
        digits = re.sub(r"[^\d]", "", str(raw))
        if not digits:
            continue
        price = round(int(digits) / 100, 2)
        if price <= 0:
            continue
        title = (ad.get("subject") or query)[:80]
        ad_id = ad.get("ad_id") or ad.get("id", "")
        link = "https://www.kufar.by/item/" + str(ad_id)
        results.append({"source": "Куфар", "name": title, "price": price, "url": link})
    results.sort(key=lambda x: x["price"])
    return results[:MAX_PER_SOURCE]


# -------- Lamoda --------
def lamoda_search(query):
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Referer": "https://www.lamoda.by/",
    }
    fallback_url = "https://www.lamoda.by/catalogsearch/result/?q=" + quote(query)
    try:
        r = requests.get(fallback_url, headers=headers, timeout=16)
        if r.status_code in (403, 429, 503):
            return []  # жёсткая блокировка
        # Ищем JSON-объекты schema.org Product
        # Lamoda встраивает данные в __NEXT_DATA__ / application/ld+json
        # Сначала пробуем ld+json
        ld_blocks = re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            r.text, re.S
        )
        for block in ld_blocks:
            try:
                obj = json.loads(block)
            except Exception:
                continue
            items = obj if isinstance(obj, list) else [obj]
            for it in items:
                if it.get("@type") not in ("Product", "ItemList"):
                    continue
                offers = it.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price_val = offers.get("price") or offers.get("lowPrice")
                if not price_val:
                    continue
                price = round(float(str(price_val).replace(",", ".")), 2)
                name = (it.get("name") or query)[:80]
                link = it.get("url") or fallback_url
                results.append({"source": "Lamoda", "name": name, "price": price, "url": link})
        if not results:
            # Запасной вариант: ищем цены в суровом HTML
            prices_raw = re.findall(r'class="[^"]*price[^"]*"[^>]*>\s*([\d\s\u00a0]+)\s*(?:BYN|BYR|руб)', r.text, re.I)
            hrefs = re.findall(r'href="(/p/[^"?#]+)"', r.text)
            names_raw = re.findall(r'class="[^"]*title[^"]*"[^>]*>\s*([^<]{5,80})\s*<', r.text)
            for i, p in enumerate(prices_raw[:MAX_PER_SOURCE]):
                clean = re.sub(r'[\s\u00a0]', '', p)
                if not clean.isdigit():
                    continue
                price = float(clean)
                name = names_raw[i].strip() if i < len(names_raw) else query[:80]
                link = ("https://www.lamoda.by" + hrefs[i]) if i < len(hrefs) else fallback_url
                results.append({"source": "Lamoda", "name": name[:80], "price": price, "url": link})
    except Exception as e:
        print(f"    Lamoda error: {e}")
    results.sort(key=lambda x: x["price"])
    return results[:MAX_PER_SOURCE]


# -------- Главная функция --------
def main():
    items = data.all_items()  # [(name, price, purpose, desc, priority, item_id)]
    total = len(items)
    print(f"Старт. Товаров: {total}")
    prices = {}
    for i, item in enumerate(items):
        item_id, cat, name, ref_price, purpose, desc, priority = item
        print(f"[{i+1}/{total}] {name}")
        variants = []
        variants += wb_search(name);      time.sleep(0.5)
        variants += kufar_search(name);   time.sleep(0.5)
        variants += lamoda_search(name);  time.sleep(0.8)
        variants.sort(key=lambda x: x["price"])
        prices[item_id] = {
            "name": name,
            "ref_price": ref_price,
            "variants": variants,
        }
        print(f"  Найдено {len(variants)} вариантов")
    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "prices": prices,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    total_v = sum(len(v["variants"]) for v in prices.values())
    print(f"\nГотово! prices.json сохранён. Итого вариантов: {total_v}")


if __name__ == "__main__":
    main()
