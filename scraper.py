#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер цен: Wildberries + Куфар + Lamoda.
Запускается автоматически через GitHub Actions, результат — prices.json.
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

from data import PURCHASES

MAX_PER_SOURCE = 2
OUT_FILE = "prices.json"

# Куфар: целевой размер выборки и параметры постраничной навигации.
MAX_KUFAR_ADS = 200      # сколько объявлений максимум собираем на запрос
KUFAR_PAGE_SIZE = 30     # размер одной страницы API
MAX_KUFAR_PAGES = 12     # жёсткий предел по страницам (защита от бесконечного цикла)

TOP_N = 14               # общий предел топ-предложений на товар
KUFAR_SHOW = 5           # сколько объявлений Куфара показывать (3–5 самых дешёвых)
OTHER_SHOW = 2           # сколько показывать с каждой другой площадки

# Кроссовки: допустимые размеры EU (45–46 ± приближённые).
ALLOWED_SHOE_SIZES = {44.5, 45.0, 45.5, 46.0, 46.5}

# Размер с явным маркером (EU/размер/р.), десятичный (45.5) и диапазон (45-46).
_SIZE_CTX_RE = re.compile(
    r"(?:eu|евро|размер|разм|р-?р|р\.|size)\s*[:№#]*\s*(4[0-8](?:[.,]5)?)",
    re.I,
)
_SIZE_DEC_RE = re.compile(r"(?<!\d)(4[0-8][.,]5)(?!\d)")
_SIZE_RANGE_RE = re.compile(r"(?<!\d)(4[0-8])\s*[-–/]\s*(4[0-8])(?!\d)")
_SIZE_STANDALONE_RE = re.compile(r"(?<!\d)(4[0-8])(?!\d)")


def _fmt_size(s):
    return ("%g" % s)


def extract_shoe_sizes(q, name):
    """Возвращает множество размеров (float), найденных в названии объявления.

    Сначала ищем размеры с явным маркером и десятичные/диапазоны (они однозначны).
    Затем — отдельно стоящие числа 40–48, НО предварительно вырезаем цифры
    из названия модели (например Pegasus 41), чтобы не принять номер модели за размер.
    """
    t = str(name or "")
    sizes = set()
    for m in _SIZE_CTX_RE.finditer(t):
        sizes.add(float(m.group(1).replace(",", ".")))
    for m in _SIZE_DEC_RE.finditer(t):
        sizes.add(float(m.group(1).replace(",", ".")))
    for m in _SIZE_RANGE_RE.finditer(t):
        a, b = int(m.group(1)), int(m.group(2))
        for s in range(min(a, b), max(a, b) + 1):
            sizes.add(float(s))
    # Отдельно стоящие числа — после удаления цифр модели из запроса.
    cleaned = t
    for num in sorted(set(re.findall(r"\d+", str(q or ""))), key=len, reverse=True):
        cleaned = re.sub(r"(?<!\d)" + re.escape(num) + r"(?!\d)", " ", cleaned)
    for m in _SIZE_STANDALONE_RE.finditer(cleaned):
        sizes.add(float(m.group(1)))
    return sizes


def shoe_size_ok(q, name):
    """(ok, строка_размера) для кроссовок.

    Правило: отсекаем ТОЛЬКО те, где размер точно определён и он не в диапазоне.
    Если размер определить не удалось (новые товары, размер выбирается при покупке)
    — НЕ отсекаем, чтобы не потерять валидные предложения.
    """
    sizes = extract_shoe_sizes(q, name)
    if not sizes:
        return True, ""
    good = sorted(s for s in sizes if s in ALLOWED_SHOE_SIZES)
    if good:
        return True, "/".join(_fmt_size(s) for s in good)
    return False, ""


def _agg(vals):
    """Мин/среднее/макс/кол-во по списку цен (или None если пусто)."""
    vals = [v for v in vals if isinstance(v, (int, float)) and v > 0]
    if not vals:
        return None
    return {
        "min": round(min(vals), 2),
        "avg": round(sum(vals) / len(vals), 2),
        "max": round(max(vals), 2),
        "count": len(vals),
    }


def compute_stats(variants):
    """Статистика цен: общая и по каждой площадке."""
    by = {}
    for v in variants:
        by.setdefault(v.get("source", "?"), []).append(v.get("price", 0))
    by_source = {s: _agg(p) for s, p in by.items()}
    by_source = {s: a for s, a in by_source.items() if a}
    return {
        "overall": _agg([v.get("price", 0) for v in variants]),
        "by_source": by_source,
    }


def build_top(variants, top_n=TOP_N):
    """Топ-предложения с квотой по площадкам.

    Куфар — до KUFAR_SHOW (3–5) самых дешёвых объявлений, каждая другая
    площадка — до OTHER_SHOW. Общий предел — top_n. Самое дешёвое
    с каждой площадки гарантированно попадает (квота ≥ 1).
    """
    ordered = sorted(variants, key=lambda v: v.get("price", 0))
    quota = {}
    top = []
    for v in ordered:
        s = v.get("source")
        cap = KUFAR_SHOW if s == "Куфар" else OTHER_SHOW
        if quota.get(s, 0) < cap:
            quota[s] = quota.get(s, 0) + 1
            top.append(v)
        if len(top) >= top_n:
            break
    top.sort(key=lambda v: v.get("price", 0))
    return top

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "application/json, text/html, */*",
}


def get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=14)
        r.raise_for_status()
        return r
    except Exception:
        return None


TOKEN_RE = r"[a-z0-9а-яё]+"


def is_relevant(q, name):
    """Отсекает нерелевантные результаты поиска.

    Модельные токены с цифрами (965, h10, kd900) обязаны присутствовать
    в названии, из остальных слов — минимум 60%.
    """
    name_l = (name or "").lower()
    name_tokens = set(re.findall(TOKEN_RE, name_l))
    tokens = [t for t in re.findall(TOKEN_RE, q.lower())
              if len(t) > 2 or any(c.isdigit() for c in t)]
    if not tokens:
        return True
    digit_tokens = [t for t in tokens if any(c.isdigit() for c in t)]
    word_tokens = [t for t in tokens if t not in digit_tokens]
    for t in digit_tokens:
        if t not in name_tokens:
            return False
    if not word_tokens:
        return True
    hits = sum(1 for t in word_tokens
               if t in name_tokens or (len(t) >= 4 and t in name_l))
    return hits >= max(1, round(len(word_tokens) * 0.6))


def search_wb(q):
    """Wildberries (новые товары, цены в BYN)."""
    out = []
    r = get("https://search.wb.ru/exactmatch/ru/common/v4/search"
            "?appType=1&curr=byn&dest=-59202&resultset=catalog&sort=priceup"
            "&query=" + quote(q))
    if not r:
        return out
    try:
        prods = r.json().get("data", {}).get("products", [])
    except Exception:
        return out
    for p in prods:
        price = (p.get("salePriceU") or p.get("priceU") or 0) / 100
        if price >= 5:
            out.append({
                "source": "Wildberries",
                "name": (p.get("brand", "") + " " + p.get("name", "")).strip()[:80],
                "price": round(price, 2),
                "url": "https://www.wildberries.by/catalog/%s/detail.aspx" % p.get("id"),
            })
        if len(out) >= 8:
            break
    return out


def get_json(url, tries=3):
    """GET с вежливым отступлением.

    Работаем ТОЛЬКО с публичным JSON-API, которым пользуется сам сайт Куфара.
    Никакой маскировки под человека и обхода защиты: если сайт отвечает
    429/503 — ждём и повторяем пару раз, если и дальше блокирует —
    честно сдаёмся и возвращаем None (не «пробиваем» защиту).
    """
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=14)
        except Exception:
            time.sleep(1.5)
            continue
        if r.status_code in (429, 503):
            # Сайт просит притормозить — уважаем это и ждём дольше.
            wait = int(r.headers.get("Retry-After", 0)) or (2 * (attempt + 1))
            time.sleep(min(wait, 10))
            continue
        if r.status_code in (403, 401):
            # Доступ ограничен — не пытаемся обходить, просто выходим.
            return None
        try:
            r.raise_for_status()
            return r.json()
        except Exception:
            return None
    return None


def _kufar_next_cursor(data):
    """Извлекает токен следующей страницы из ответа, если он есть.

    Устойчив к разным форматам: pagination.pages[label=='next'].token
    либо pagination.token. Если ничего нет — возвращает None (конец).
    """
    if not isinstance(data, dict):
        return None
    pag = data.get("pagination")
    if not isinstance(pag, dict):
        return None
    for pg in (pag.get("pages") or []):
        if isinstance(pg, dict) and pg.get("label") == "next":
            tok = pg.get("token")
            if tok:
                return str(tok)
    tok = pag.get("token")
    return str(tok) if tok else None


def _parse_kufar_ad(ad, seen):
    """Разбирает одно объявление. Возвращает dict или None.

    Никогда не падает: любой кривой элемент просто пропускается.
    """
    if not isinstance(ad, dict):
        return None
    # Цена: сначала price_byn (копейки), запасной вариант — list_price.
    raw = ad.get("price_byn")
    if raw in (None, "", 0, "0"):
        lp = ad.get("list_price")
        raw = lp.get("amount") if isinstance(lp, dict) else None
    try:
        price = int(str(raw).strip()) / 100
    except (TypeError, ValueError):
        return None
    if price < 5:
        return None
    link = ad.get("ad_link") or ad.get("ad_url") or ""
    if not isinstance(link, str) or not link or link in seen:
        return None
    seen.add(link)
    # Регион и состояние — из параметров объявления, если они есть.
    region = ""
    condition = ""
    params = ad.get("ad_parameters")
    if isinstance(params, list):
        for p in params:
            if not isinstance(p, dict):
                continue
            pl = str(p.get("pl") or "").lower()
            if p.get("p") == "area" or "област" in pl or "город" in pl:
                region = p.get("vl") or region
            if p.get("p") == "condition" or "состоя" in pl:
                condition = p.get("vl") or condition
    name = str(ad.get("subject") or "").strip()
    if condition:
        name = f"{name} · {condition}"
    return {
        "source": "Куфар",
        "name": name[:80],
        "price": round(price, 2),
        "url": link,
        "region": str(region or ""),
    }


def search_kufar(q, target=MAX_KUFAR_ADS):
    """Куфар — публичный поисковый API (тот же, что у сайта kufar.by).

    Собирает до `target` объявлений (по умолчанию 200) через постраничную
    навигацию с вежливыми паузами. Цены — в копейках (price_byn).
    Функция никогда не падает: при любой ошибке возвращает то, что успела собрать.
    """
    out = []
    seen = set()
    try:
        target = max(1, min(int(target), 500))
    except (TypeError, ValueError):
        target = MAX_KUFAR_ADS
    cursor = None
    for _ in range(MAX_KUFAR_PAGES):
        url = ("https://api.kufar.by/search-api/v2/search/rendered-paginated"
               "?lang=ru&size=%d&sort=price_asc&query=%s"
               % (KUFAR_PAGE_SIZE, quote(q)))
        if cursor:
            url += "&cursor=" + quote(cursor)
        data = get_json(url)
        if not isinstance(data, dict):
            break  # сеть/блокировка/мусор — отдаём то, что есть
        ads = data.get("ads")
        if not isinstance(ads, list) or not ads:
            break  # пустая страница — конец выдачи
        for ad in ads:
            row = _parse_kufar_ad(ad, seen)
            if row:
                out.append(row)
                if len(out) >= target:
                    return out
        cursor = _kufar_next_cursor(data)
        if not cursor:
            break  # следующей страницы нет
        time.sleep(0.6)  # вежливая пауза между страницами
    return out


def search_lamoda(q):
    """Lamoda (новые товары). Парсим schema.org разметку из HTML."""
    out = []
    r = get("https://www.lamoda.by/catalogsearch/result/?q=" + quote(q))
    if not r:
        return out
    html = r.text
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        items = data.get("itemListElement") or []
        for el in items:
            prod = el.get("item", el) if isinstance(el, dict) else {}
            offers = prod.get("offers") or {}
            try:
                price = float(offers.get("price") or offers.get("lowPrice") or 0)
            except Exception:
                continue
            if price >= 5:
                out.append({
                    "source": "Lamoda",
                    "name": (prod.get("name") or "")[:80],
                    "price": round(price, 2),
                    "url": prod.get("url") or "",
                })
            if len(out) >= 8:
                return out
    if out:
        return out
    # запасной вариант: цены прямо из HTML
    prices = re.findall(r'"price"\s*:\s*"?([0-9]{2,5}(?:\.[0-9]+)?)"?', html)
    for p in prices[:8]:
        try:
            price = float(p)
        except Exception:
            continue
        if price >= 5:
            out.append({"source": "Lamoda", "name": q, "price": round(price, 2),
                        "url": "https://www.lamoda.by/catalogsearch/result/?q=" + quote(q)})
    return out


def search_onliner(q):
    """Onliner Каталог — агрегатор цен сотен магазинов Беларуси."""
    out = []
    r = get("https://catalog.onliner.by/sdapi/catalog.api/search/products?query=" + quote(q))
    if not r:
        return out
    try:
        prods = r.json().get("products", [])
    except Exception:
        return out
    for p in prods:
        pr = (p.get("prices") or {}).get("price_min") or {}
        try:
            price = float(pr.get("amount") or 0)
        except Exception:
            continue
        if price >= 5:
            out.append({
                "source": "Onliner",
                "name": (p.get("full_name") or p.get("name") or "")[:80],
                "price": round(price, 2),
                "url": p.get("html_url") or "",
            })
        if len(out) >= 8:
            break
    return out


def collect_item(name, is_shoe):
    """Собирает все релевантные варианты по одному товару со всех площадок."""
    variants = []
    for fn in (search_wb, search_kufar, search_lamoda, search_onliner):
        try:
            found = [v for v in fn(name) if is_relevant(name, v.get("name", ""))]
        except Exception as e:
            print("  !", fn.__name__, e)
            found = []
        if is_shoe:
            kept = []
            for v in found:
                ok, sz = shoe_size_ok(name, v.get("name", ""))
                if ok:
                    if sz:
                        v["size"] = sz
                    kept.append(v)
            found = kept
        variants += found
        time.sleep(0.4)
    # Дедупликация и отсев невалидных цен.
    seen = set()
    uniq = []
    for v in variants:
        if v.get("price", 0) <= 0:
            continue
        k = v.get("url") or (str(v.get("source")) + str(v.get("name")) + str(v.get("price")))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(v)
    return uniq


def main():
    prices = {}
    total = sum(len(c["items"]) for c in PURCHASES)
    n = 0
    for ci, cat in enumerate(PURCHASES):
        is_shoe = "Кроссовк" in cat.get("cat", "")
        for ii, item in enumerate(cat["items"]):
            n += 1
            name = item[0]
            print(f"[{n}/{total}] {name}" + (" [размер 45-46]" if is_shoe else ""))
            variants = collect_item(name, is_shoe)
            if variants:
                prices[f"{ci}:{ii}"] = {
                    "variants": build_top(variants),
                    "stats": compute_stats(variants),
                }
    minsk = timezone(timedelta(hours=3))
    out = {
        "updated": datetime.now(minsk).strftime("%d.%m.%Y %H:%M"),
        "prices": prices,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Готово: цены найдены для {len(prices)} товаров")


if __name__ == "__main__":
    main()
