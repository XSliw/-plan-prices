# -*- coding: utf-8 -*-
"""Оффлайн-стресс-тесты для search_kufar.

Запуск: python3 test_scraper.py
Имитируем все мыслимые ответы сервера (без реальной сети) и проверяем,
что парсер НИКОГДА не падает и корректно деградирует.
"""
import json
import sys
import types

import scraper

# Отключаем реальные паузы, чтобы тесты шли мгновенно.
scraper.time.sleep = lambda *a, **k: None

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓", name)
    else:
        FAIL += 1
        print("  ✗ ПРОВАЛ:", name)


class FakeResp:
    def __init__(self, status=200, payload=None, text="", raise_json=False,
                 headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text
        self._raise_json = raise_json
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP %d" % self.status_code)

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


def make_ad(i, price="10000", link=None, subject="Adidas Adizero Evo SL"):
    return {
        "price_byn": price,
        "ad_link": link or ("https://www.kufar.by/item/%d" % i),
        "subject": subject,
        "ad_parameters": [
            {"p": "area", "pl": "Область", "vl": "Минск"},
            {"p": "condition", "pl": "Состояние", "vl": "Б/у"},
        ],
    }


def page(ads, next_token=None):
    pag = {"pages": []}
    if next_token:
        pag["pages"].append({"label": "next", "token": next_token})
    return {"ads": ads, "pagination": pag}


def install(seq):
    """seq — список FakeResp или исключений, выдаётся по очереди."""
    calls = {"n": 0}

    def fake_get(url, headers=None, timeout=None):
        i = calls["n"]
        calls["n"] += 1
        item = seq[i] if i < len(seq) else seq[-1]
        if isinstance(item, Exception):
            raise item
        return item

    scraper.requests.get = fake_get
    return calls


# ---------------------------------------------------------------------------
print("1. Нормальная постраничная выборка до 200")
seq = []
cnt = 0
for pageno in range(10):  # 10 страниц по 30 = 300 объявлений
    ads = [make_ad(cnt + j) for j in range(30)]
    cnt += 30
    tok = "t%d" % pageno if pageno < 9 else None
    seq.append(FakeResp(200, page(ads, tok)))
install(seq)
res = scraper.search_kufar("Adidas Adizero Evo SL", target=200)
check("собрано ровно 200", len(res) == 200)
check("все с полем source=Куфар", all(r["source"] == "Куфар" for r in res))
check("цена = 100.0 (копейки → рубли)", res[0]["price"] == 100.0)
check("состояние в названии", "Б/у" in res[0]["name"])
check("регион заполнен", res[0]["region"] == "Минск")

print("2. Выдача короче target (конец без next-токена)")
install([FakeResp(200, page([make_ad(i) for i in range(12)], None))])
res = scraper.search_kufar("x", target=200)
check("собрано 12 и остановились", len(res) == 12)

print("3. Пустая выдача")
install([FakeResp(200, page([], None))])
check("пустой список", scraper.search_kufar("x") == [])

print("4. 429 трижды → все попытки исчерпаны")
install([FakeResp(429, headers={"Retry-After": "1"})])
check("не упало, пусто", scraper.search_kufar("x") == [])

print("5. 429 один раз, потом 200")
install([FakeResp(429, headers={"Retry-After": "0"}),
         FakeResp(200, page([make_ad(1)], None))])
res = scraper.search_kufar("x")
check("восстановились после 429", len(res) == 1)

print("6. 403 — доступ закрыт, не обходим")
install([FakeResp(403)])
check("пусто, без падения", scraper.search_kufar("x") == [])

print("7. 500 серверная ошибка")
install([FakeResp(500)])
check("пусто, без падения", scraper.search_kufar("x") == [])

print("8. Кривой JSON")
install([FakeResp(200, None, raise_json=True)])
check("пусто, без падения", scraper.search_kufar("x") == [])

print("9. Сетевое исключение (timeout)")
install([TimeoutError("boom")])
check("пусто, без падения", scraper.search_kufar("x") == [])

print("10. Мусор вместо dict (список/число/None)")
for junk in ([1, 2, 3], 42, None, "strka", True):
    install([FakeResp(200, junk)])
    check("junk=%r → []" % (junk,), scraper.search_kufar("x") == [])

print("11. ads не список")
install([FakeResp(200, {"ads": {"foo": "bar"}, "pagination": {}})])
check("пусто", scraper.search_kufar("x") == [])

print("12. Объявления-мусор внутри списка")
bad_ads = [None, 42, "str", [], {}, {"price_byn": "abc"},
           {"price_byn": "10000"},  # нет ссылки
           {"price_byn": "200", "ad_link": "u1", "subject": "ok"},  # < 5 руб -> цена 2.0 отсечётся
           {"price_byn": "90000", "ad_link": "u2", "subject": "хорошее",
            "ad_parameters": "не список"}]
install([FakeResp(200, page(bad_ads, None))])
res = scraper.search_kufar("x")
check("выжило только 1 валидное", len(res) == 1 and res[0]["url"] == "u2")
check("битые ad_parameters не сломали", res[0]["region"] == "")

print("13. Дубли по ссылке между страницами")
p1 = page([make_ad(1, link="dup"), make_ad(2, link="a")], "n1")
p2 = page([make_ad(3, link="dup"), make_ad(4, link="b")], None)
install([FakeResp(200, p1), FakeResp(200, p2)])
res = scraper.search_kufar("x")
check("дубликат схлопнулся (3 уник.)", len(res) == 3)
urls = [r["url"] for r in res]
check("dup только один раз", urls.count("dup") == 1)

print("14. Защита от бесконечного цикла (всегда есть next)")
counter = {"n": 0}


def endless_get(url, headers=None, timeout=None):
    counter["n"] += 1
    return FakeResp(200, page([make_ad(counter["n"] * 1000 + j) for j in range(30)], "tok"))


scraper.requests.get = endless_get
res = scraper.search_kufar("x", target=100000)  # недостижимое число
check("не больше MAX_KUFAR_PAGES запросов", counter["n"] <= scraper.MAX_KUFAR_PAGES)
check("target ограничен сверху (<=500)", len(res) <= 500)

print("15. target мусор (None/строка/0/отриц.)")
for t in (None, "abc", 0, -5, 3.9):
    install([FakeResp(200, page([make_ad(i) for i in range(30)], None))])
    r = scraper.search_kufar("x", target=t)
    check("target=%r не сломало" % (t,), isinstance(r, list))

print("16. price_byn как int, и запасной list_price")
ads = [
    {"price_byn": 90000, "ad_link": "i1", "subject": "int-цена"},
    {"price_byn": None, "list_price": {"amount": "75000"}, "ad_link": "i2", "subject": "lp"},
    {"price_byn": "", "list_price": {"amount": 50000}, "ad_link": "i3", "subject": "lp2"},
]
install([FakeResp(200, page(ads, None))])
res = scraper.search_kufar("x")
check("разобраны все 3 формата цены", len(res) == 3)
check("int-цена = 900.0", res[0]["price"] == 900.0)

print("17. JSON-сериализация результата (как в prices.json)")
install([FakeResp(200, page([make_ad(i) for i in range(5)], None))])
res = scraper.search_kufar("x")
try:
    json.dumps({"variants": res}, ensure_ascii=False)
    ok = True
except Exception:
    ok = False
check("результат сериализуется в JSON", ok)

print("18. is_relevant не отсекает валидный матч и режет мусор")
check("точное совпадение", scraper.is_relevant("Polar H10", "Датчик Polar H10 новый"))
check("модельный токен обязателен", not scraper.is_relevant("Garmin 965", "Garmin 265"))

print()
print("=" * 44)
print("ИТОГО: %d пройдено, %d провалено" % (PASS, FAIL))
print("=" * 44)
sys.exit(1 if FAIL else 0)
