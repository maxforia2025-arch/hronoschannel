#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🖼 КАРТИНКИ ИЗ ИНТЕРНЕТА для постов «Хроноса» — Викисклад (Wikimedia Commons).

Почему именно Викисклад, а не поиск картинок: там public domain и свободные
лицензии. Произвольное фото из выдачи почти всегда принадлежит агентству
(AP, Getty) — публикация такого в канале это претензия и штраф.
Здесь же лежат подлинные архивные снимки событий, что документальному
каналу подходит лучше любой генерации.

Лицензии: PD — можно без указания автора; CC BY / CC BY-SA — ОБЯЗАТЕЛЬНО
указание автора и лицензии, оно пишется в credits.json и подставляется
в подпись поста. Всё несвободное отбрасывается.

Запуск:
    python3 fetch_images.py              # скачать всем постам без картинки
    python3 fetch_images.py --id X,Y     # только этим
    python3 fetch_images.py --force      # перекачать, даже если картинка есть
    python3 fetch_images.py --dry-run    # показать, что нашлось, ничего не качать
"""

import argparse
import json
import os
import re
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "img")
CREDITS_PATH = os.path.join(IMG_DIR, "credits.json")
POSTS_PATH = os.path.join(HERE, "posts.json")
UA = "hronos-bot/1.0 (https://t.me/hronos_channel; maxforia2025@gmail.com)"

# Лицензии, которые пропускаем. Всё остальное — мимо.
OK_LICENSE = re.compile(r"public domain|^cc0|^cc by(?!.*nc)|^pd", re.I)
NEEDS_CREDIT = re.compile(r"^cc by", re.I)

# Поисковые запросы под каждый пост. Точность важнее автоматики:
# выдача по заголовку поста тянет случайное, поэтому запрос задан руками.
QUERIES = {
    "odin_den_01": "Berlin Wall November 1989 Bornholmer Strasse crossing",
    "razvilka_02": "Stanislav Petrov memorial",
    "tihiy_fakt_03": "Bockscar B-29 Superfortress",
    "karta_04": "Berlin Conference 1884 Africa Kongokonferenz",
    "odin_den_05": "Apollo 11 Lunar Module",
    "razvilka_06": "Franz Ferdinand Sarajevo assassination 1914 car",
    "tihiy_fakt_07": "Soviet submarine B-59 1962 Cuban Missile Crisis",
    "karta_08": "Treaty of Tordesillas 1494",
    "odin_den_09": "D-Day Normandy landing 6 June 1944",
    "razvilka_10": "Alexander Fleming laboratory penicillin",
    "tihiy_fakt_11": "RMS Titanic departing Southampton April 1912",
    "karta_12": "Alaska Purchase",
    "odin_den_13": "Yuri Gagarin cosmonaut portrait 1961",
    "razvilka_14": "Winston Churchill 1940 war cabinet",
    "tihiy_fakt_15": "John Snow cholera map Broad Street pump 1854",
    "odin_den_16": "IAEA Chernobyl 02790015",
    "odin_den_17": "Pompeii ruins photograph Vesuvius",
    "odin_den_18": "1755 Lisbon earthquake tsunami engraving",
    "odin_den_19": "Wright Flyer first flight 17 December 1903",
    "odin_den_20": "Storming of the Bastille 14 July 1789 painting",
    "razvilka_21": "John Harrison chronometer",
    "razvilka_22": "Alexander Graham Bell speaking into telephone 1876",
    "razvilka_23": "Hinckley First Operation Under Ether painting",
    "razvilka_24": "Apollo 1 command module 1967 crew",
    "razvilka_25": "Rosa Parks 1955 Montgomery bus",
    "tihiy_fakt_26": "Opana radar station Pearl Harbor 1941",
    "tihiy_fakt_27": "Trinity nuclear test 16 July 1945 explosion",
    "tihiy_fakt_28": "Krakatoa 1883 eruption lithograph Royal Society",
    "tihiy_fakt_29": "DNA structure model Crick Watson",
    "tihiy_fakt_30": "first medical X-ray hand rings 1895 Rontgen",
    "karta_31": "Berliner Mauer Bau 1961 Stacheldraht",
    "karta_32": "Partition of India 1947 refugee train Punjab",
    "karta_33": "Mount Tambora caldera Sumbawa",
    "karta_34": "Thames pollution 1858 cartoon Punch",
    "karta_35": "Columbus landing 1492 Santa Maria",
}

# Отсеиваем мусор в названиях файлов: гербы, флаги, схемы-заглушки, карты-локаторы.
BAD_TITLE = re.compile(
    r"coat of arms|flag of|locator|blank map|logo|icon|stub|signature|"
    r"collage|stamp|briefmarke|postage|banknote|coin|"
    r"\.svg$|map of the world", re.I)


def log(msg):
    print("[img] " + str(msg), flush=True)


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.load(resp)


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def search(query, limit=8):
    """Кандидаты с Викисклада: только свободные лицензии, только растр."""
    data = api({
        "action": "query", "format": "json", "generator": "search",
        "gsrnamespace": "6", "gsrlimit": str(limit), "gsrsearch": query,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": "1600",
    })
    out = []
    for page in (data.get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        title = page.get("title", "")
        if not info.get("thumburl"):
            continue
        if (info.get("mime") or "").split("/")[-1] not in ("jpeg", "png", "jpg"):
            continue
        if BAD_TITLE.search(title):
            continue
        if not OK_LICENSE.search(lic):
            continue
        if (info.get("width") or 0) < 600:
            continue
        out.append({
            "title": title,
            "license": lic,
            "author": strip_html(meta.get("Artist", {}).get("value", "")) or "неизвестен",
            "descr_url": info.get("descriptionurl", ""),
            "thumb": info.get("thumburl"),
            "width": info.get("width"),
        })
    # public domain вперёд: с ним не нужна подпись об авторстве
    out.sort(key=lambda c: (0 if not NEEDS_CREDIT.search(c["license"]) else 1,
                            -(c["width"] or 0)))
    return out


def download(url, path, tries=3):
    """Викисклад иногда рвёт соединение на середине — поэтому повторы."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) < 5000:                 # подозрительно мало — не картинка
                raise IOError("файл слишком мал: %d байт" % len(data))
            with open(path, "wb") as fh:
                fh.write(data)
            return len(data)
        except Exception as exc:
            last = exc
            log("   попытка %d не удалась (%s)" % (attempt + 1, exc))
    raise last


def has_image(pid):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if os.path.exists(os.path.join(IMG_DIR, pid + ext)):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Картинки с Викисклада для постов «Хроноса»")
    ap.add_argument("--id", default="", help="только эти посты, через запятую")
    ap.add_argument("--force", action="store_true", help="перекачать, даже если картинка есть")
    ap.add_argument("--dry-run", action="store_true", help="показать находки, не качать")
    args = ap.parse_args()

    os.makedirs(IMG_DIR, exist_ok=True)
    posts = json.load(open(POSTS_PATH, encoding="utf-8"))
    credits = {}
    if os.path.exists(CREDITS_PATH):
        credits = json.load(open(CREDITS_PATH, encoding="utf-8"))

    wanted = [x.strip() for x in args.id.split(",") if x.strip()]
    ids = [p["id"] for p in posts if p.get("id") in QUERIES]
    if wanted:
        ids = [i for i in ids if i in wanted]

    got = skipped = missed = 0
    for pid in ids:
        if has_image(pid) and not args.force:
            skipped += 1
            continue
        cands = search(QUERIES[pid])
        if not cands:
            log("НЕ НАЙДЕНО: " + pid + " (" + QUERIES[pid] + ")")
            missed += 1
            continue
        best = cands[0]
        mark = "" if not NEEDS_CREDIT.search(best["license"]) else "  ← нужна подпись автора"
        log("%-15s %-16s %s%s" % (pid, best["license"], best["title"][5:60], mark))
        if args.dry_run:
            continue
        path = os.path.join(IMG_DIR, pid + ".jpg")
        try:
            size = download(best["thumb"], path)
        except Exception as exc:
            log("   НЕ СКАЧАНО: " + pid + " (" + str(exc) + ")")
            missed += 1
            continue
        credits[pid] = {
            "title": best["title"], "license": best["license"],
            "author": best["author"], "source": best["descr_url"],
        }
        got += 1
        log("   сохранено %d КБ" % (size // 1024))
        with open(CREDITS_PATH, "w", encoding="utf-8") as fh:
            json.dump(credits, fh, ensure_ascii=False, indent=1)

    if not args.dry_run:
        with open(CREDITS_PATH, "w", encoding="utf-8") as fh:
            json.dump(credits, fh, ensure_ascii=False, indent=1)
    log("скачано %d | уже было %d | не найдено %d" % (got, skipped, missed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
