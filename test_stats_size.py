# -*- coding: utf-8 -*-
"""Тесты размерного фильтра кроссовок и агрегации цен.

Запуск: python3 test_stats_size.py
"""
import sys
import scraper

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


print("A. Размер кроссовок — пропуск в диапазоне")
Q = "Nike Pegasus 41"
cases_keep = [
    "Кроссовки Nike Pegasus 41 размер 45",
    "Nike Pegasus 41 EU 46",
    "Кроссовки Nike р. 45,5",
    "Nike Pegasus 41, 44-45",
    "Nike Pegasus 41 р-р 46",
    "Nike Pegasus 41 46.5",
]
for c in cases_keep:
    ok, sz = scraper.shoe_size_ok(Q, c)
    check("ОСТАВИТЬ: %r → р.%s" % (c, sz), ok and sz)

print("B. Размер кроссовок — отсев вне диапазона")
cases_drop = [
    "Nike Pegasus 41 размер 42",
    "Nike Pegasus 41 EU 40",
    "Nike Pegasus 41 р. 43",
    "Nike Pegasus 41 47",
    "Nike Pegasus 41 43,5",
]
for c in cases_drop:
    ok, sz = scraper.shoe_size_ok(Q, c)
    check("ОТСЕЧЬ: %r" % c, not ok)

print("C. Номер модели НЕ принимается за размер")
# 41 — часть модели, не размер → размер не определён → оставляем
ok, sz = scraper.shoe_size_ok("Nike Pegasus 41", "Nike Pegasus 41 новые")
check("Pegasus 41 без размера → оставлен, size пуст", ok and sz == "")
ok, sz = scraper.shoe_size_ok("Saucony Endorphin Speed 4", "Saucony Endorphin Speed 4")
check("Speed 4 → оставлен", ok and sz == "")
ok, sz = scraper.shoe_size_ok("Kiprun KD900", "Kiprun KD900 новые")
check("KD900 (900 не размер) → оставлен", ok and sz == "")

print("D. Без размера (новые товары) — не отсекаются")
ok, sz = scraper.shoe_size_ok("Hoka Clifton 9", "Hoka Clifton 9 мужские")
check("без размера → оставлен", ok and sz == "")

print("E. Агрегация цен (min/avg/max/count)")
vs = [
    {"source": "Куфар", "price": 100.0},
    {"source": "Куфар", "price": 200.0},
    {"source": "Wildberries", "price": 300.0},
    {"source": "Onliner", "price": 150.0},
]
st = scraper.compute_stats(vs)
check("overall.min=100", st["overall"]["min"] == 100.0)
check("overall.max=300", st["overall"]["max"] == 300.0)
check("overall.avg=187.5", st["overall"]["avg"] == 187.5)
check("overall.count=4", st["overall"]["count"] == 4)
check("Куфар.avg=150", st["by_source"]["Куфар"]["avg"] == 150.0)
check("Куфар.count=2", st["by_source"]["Куфар"]["count"] == 2)
check("3 площадки", len(st["by_source"]) == 3)

print("F. Агрегация пустого / мусора")
check("пусто → overall=None", scraper.compute_stats([])["overall"] is None)
check("отриц/ноль отсеяны",
      scraper._agg([0, -5, "x", None, 50]) == {"min": 50, "avg": 50, "max": 50, "count": 1})

print("G. build_top: квоты — Куфар до 5, остальные до 2, сортировка по цене")
big = []
for i in range(50):
    big.append({"source": "Куфар", "price": 10.0 + i, "url": "k%d" % i})
big.append({"source": "Wildberries", "price": 999.0, "url": "wb1"})
big.append({"source": "Onliner", "price": 888.0, "url": "on1"})
top = scraper.build_top(big)
kufar_cnt = sum(1 for v in top if v["source"] == "Куфар")
check("Куфара ровно 5 (квота, не все 50)", kufar_cnt == scraper.KUFAR_SHOW == 5)
check("Куфар — именно самые дешёвые (10..14)",
      sorted(v["price"] for v in top if v["source"] == "Куфар") == [10.0, 11.0, 12.0, 13.0, 14.0])
check("всего 7 (5 Куфар + WB + Onliner)", len(top) == 7)
check("отсортировано по цене", all(top[i]["price"] <= top[i + 1]["price"] for i in range(len(top) - 1)))
srcs = {v["source"] for v in top}
check("WB представлен несмотря на высокую цену", "Wildberries" in srcs)
check("Onliner представлен", "Onliner" in srcs)
# Если Куфара меньше 5 — показываем сколько есть (3)
small = [{"source": "Куфар", "price": 10.0 + i, "url": "s%d" % i} for i in range(3)]
check("Куфара 3 из 3 когда мало объявлений", len(scraper.build_top(small)) == 3)

print("H. Интеграция collect_item с мок-площадками + размерный фильтр")
scraper.time.sleep = lambda *a, **k: None
scraper.search_wb = lambda q: [{"source": "Wildberries", "name": "Adidas Adizero Evo SL", "price": 330.0, "url": "wb"}]
scraper.search_lamoda = lambda q: []
scraper.search_onliner = lambda q: [{"source": "Onliner", "name": "Adidas Adizero Evo SL", "price": 300.0, "url": "on"}]
scraper.search_kufar = lambda q, target=200: [
    {"source": "Куфар", "name": "Adidas Adizero Evo SL размер 45", "price": 150.0, "url": "k1"},
    {"source": "Куфар", "name": "Adidas Adizero Evo SL р. 42", "price": 120.0, "url": "k2"},  # отсечётся
    {"source": "Куфар", "name": "Adidas Adizero Evo SL EU 46", "price": 170.0, "url": "k3"},
]
res = scraper.collect_item("Adidas Adizero Evo SL", is_shoe=True)
urls = {v["url"] for v in res}
check("размер 42 отсечён", "k2" not in urls)
check("размеры 45 и 46 остались", "k1" in urls and "k3" in urls)
check("новые (без размера) WB/Onliner остались", "wb" in urls and "on" in urls)
k1 = next(v for v in res if v["url"] == "k1")
check("у k1 проставлен size=45", k1.get("size") == "45")
st = scraper.compute_stats(res)
check("в статистике 3 площадки", len(st["by_source"]) == 3)
check("overall.min=150 (самое дешёвое валидное)", st["overall"]["min"] == 150.0)

print()
print("=" * 44)
print("ИТОГО: %d пройдено, %d провалено" % (PASS, FAIL))
print("=" * 44)
sys.exit(1 if FAIL else 0)
