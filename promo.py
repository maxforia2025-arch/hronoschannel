#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔁 ЕЖЕНЕДЕЛЬНАЯ КРОСС-РЕКЛАМА сети Maxforia Group в канале «Хронос».

Одно воскресенье = один канал сети, строго по кругу (promo.json).
Креатив внутри канала меняется на каждом новом круге — за три круга
ни один текст не повторится.

Только стандартная библиотека. Работает в GitHub Actions при выключенном Mac.
Карточка рисуется кодом (SVG → PNG через rsvg-convert), генерация не нужна.

Запуск:
    python3 promo.py                # DRY-RUN: показать, что уйдёт, ничего не слать
    python3 promo.py --send         # реальная отправка
    python3 promo.py --plan 6       # расписание на 6 воскресений вперёд

Защита от дублей: счётчик недели в promo_state.json увеличивается ТОЛЬКО
после успешной отправки и коммитится обратно в репозиторий.
"""

import argparse
import html
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROMO_PATH = os.path.join(HERE, "promo.json")
STATE_PATH = os.path.join(HERE, "promo_state.json")
CONFIG_PATH = os.path.join(HERE, "config.json")
CARD_PATH = os.path.join(HERE, "promo_card.png")

# Палитра канала (brand/BRAND.md)
BG_DARK, BG_LIGHT = "#0B0C10", "#16181F"
ACCENT, TEXT, DIM = "#C0563A", "#E8E4DA", "#7C8391"
FAM = "DejaVu Sans, Liberation Sans, Helvetica, Arial, sans-serif"
W, H, MARGIN = 1080, 1350, 90


def log(msg):
    print("[promo] " + str(msg), flush=True)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_counter():
    st = load_json(STATE_PATH, {}) or {}
    try:
        return int(st.get("n", 0))
    except (TypeError, ValueError):
        return 0


def write_counter(n):
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump({"n": n}, fh, ensure_ascii=False)


def pick(cfg, n):
    """Канал недели и креатив: канал по кругу, вариант — на следующем круге."""
    channels = cfg["channels"]
    ch = channels[n % len(channels)]
    v = ch["variants"][(n // len(channels)) % len(ch["variants"])]
    return ch, v


def channel_is_live(handle, token):
    """Проверка через Bot API, что рекламируемый канал существует."""
    if not token:
        return True                      # dry-run без токена — не проверяем
    url = ("https://api.telegram.org/bot" + token + "/getChat?chat_id="
           + urllib.parse.quote(handle))
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.load(resp).get("ok", False)
    except Exception:
        return False


# ── карточка ─────────────────────────────────────────────────────────────────

def _wrap(text, limit):
    words, lines, cur = text.split(), [], ""
    for w in words:
        probe = (cur + " " + w).strip()
        if len(probe) > limit and cur:
            lines.append(cur)
            cur = w
        else:
            cur = probe
    if cur:
        lines.append(cur)
    return lines


def _tspans(text, x, y, size, step, fill, weight, limit):
    lines = _wrap(text, limit)
    out = []
    for i, ln in enumerate(lines):
        out.append('<text x="%d" y="%d" font-family="%s" font-size="%d" '
                   'font-weight="%d" fill="%s">%s</text>'
                   % (x, y + i * step, FAM, size, weight, fill, html.escape(ln)))
    return "\n  ".join(out), y + len(lines) * step


def build_card_svg(v, ch):
    """Карточка в коде «Хроноса»: тёмный фон, риска-акцент, без неона."""
    parts = []
    kicker = html.escape(v["kicker"])
    parts.append('<rect x="%d" y="150" width="8" height="56" fill="%s"/>' % (MARGIN, ACCENT))
    parts.append('<text x="%d" y="192" font-family="%s" font-size="30" font-weight="700" '
                 'fill="%s" letter-spacing="6">%s</text>'
                 % (MARGIN + 34, FAM, ACCENT, kicker))

    y = 320
    svg, y = _tspans(v["title"], MARGIN, y, 66, 84, TEXT, 700, 26)
    parts.append(svg)

    y += 40
    svg, y = _tspans(v["text"], MARGIN, y, 38, 54, DIM, 400, 44)
    parts.append(svg)

    y += 34
    svg, y = _tspans(v["pitch"], MARGIN, y, 38, 54, TEXT, 700, 44)
    parts.append(svg)

    box_y = min(y + 60, H - 300)
    parts.append('<rect x="%d" y="%d" width="%d" height="104" rx="10" fill="%s"/>'
                 % (MARGIN, box_y, W - 2 * MARGIN, ACCENT))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="40" '
                 'font-weight="700" fill="%s">%s</text>'
                 % (W // 2, box_y + 66, FAM, BG_DARK, html.escape(v["cta"])))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="46" '
                 'font-weight="700" fill="%s" letter-spacing="2">%s</text>'
                 % (W // 2, box_y + 184, FAM, TEXT, html.escape(ch["handle"])))

    body = "\n  ".join(parts)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">\n'
            '  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
            '</linearGradient></defs>\n'
            '  <rect width="%d" height="%d" fill="url(#bg)"/>\n'
            '  <circle cx="%d" cy="%d" r="150" fill="none" stroke="%s" stroke-width="3" '
            'opacity="0.10"/>\n  %s\n</svg>'
            % (W, H, W, H, BG_LIGHT, BG_DARK, W, H, W - 120, H - 140, TEXT, body))


def render_card(svg):
    """SVG → PNG. Нет rsvg-convert — работаем без картинки, текстом."""
    svg_path = CARD_PATH.replace(".png", ".svg")
    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    try:
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H),
                        "-o", CARD_PATH, svg_path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return CARD_PATH if os.path.exists(CARD_PATH) else None
    except Exception as exc:
        log("карточка не отрисована (" + str(exc) + ") — уйдёт текстом")
        return None


def build_caption(v, ch, cfg):
    name = html.escape(ch["name"])
    handle = html.escape(ch["handle"])
    own = html.escape(str(cfg.get("channel_handle", "@hronos_channel")))
    return ("⏳ <b>" + html.escape(v["kicker"]).capitalize() + "</b>\n\n"
            + html.escape(v["text"]) + "\n\n"
            + "<b>«" + name + "»</b> — " + html.escape(v["pitch"].split("—", 1)[-1].strip())
            + "\n\n👉 " + html.escape(v["cta"]) + ": " + handle
            + "\n\n➖➖➖➖➖\nЭто канал нашей сети. Мы остаёмся здесь: " + own)


# ── отправка ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Еженедельная кросс-реклама «Хроноса»")
    ap.add_argument("--send", action="store_true", help="реальная отправка")
    ap.add_argument("--plan", type=int, default=0, help="показать расписание на N воскресений")
    args = ap.parse_args()

    sys.path.insert(0, HERE)
    import post as poster                      # переиспользуем отправку из постера

    poster.load_env()
    cfg_ch = load_json(CONFIG_PATH, {}) or {}
    cfg = load_json(PROMO_PATH)
    if not cfg or not cfg.get("channels"):
        log("promo.json пуст — нечего рекламировать")
        return 1

    token = (os.environ.get("BOT_TOKEN", "")
             or os.environ.get("HRONOSCHANNELBOT", "")).strip()
    channel_id = (os.environ.get("CHANNEL_ID", "").strip()
                  or str(cfg_ch.get("channel_id_numeric") or "").strip())
    n = read_counter()

    if args.plan:
        for k in range(args.plan):
            ch, v = pick(cfg, n + k)
            log("неделя +%d: %s — «%s»" % (k, ch["handle"], v["title"]))
        return 0

    # канал недели; если он недоступен — берём следующий по кругу
    total = len(cfg["channels"])
    ch = v = None
    for step in range(total):
        cand, cand_v = pick(cfg, n + step)
        if channel_is_live(cand["handle"], token if args.send else ""):
            ch, v, n = cand, cand_v, n + step
            break
        log("канал " + cand["handle"] + " недоступен — пропускаю")
    if ch is None:
        log("ни один канал сети не доступен — ничего не публикую")
        return 1

    caption = build_caption(v, ch, cfg_ch)
    card = render_card(build_card_svg(v, ch))

    log("неделя #%d: рекламируем %s (%s)" % (n + 1, ch["name"], ch["handle"]))
    if not args.send:
        print("\n" + "=" * 56 + "\n" + caption + "\n" + "=" * 56)
        log("DRY-RUN: ничего не отправлено")
        return 0

    if not token or not channel_id:
        log("ОШИБКА: --send требует BOT_TOKEN (или HRONOSCHANNELBOT). Ничего не отправлено.")
        return 2

    if card:
        poster.send_telegram_photo(token, channel_id, caption, card)
    else:
        poster.send_telegram(token, channel_id, caption)
    write_counter(n + 1)                      # счётчик двигаем ТОЛЬКО после успеха
    log("опубликовано: реклама " + ch["handle"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
