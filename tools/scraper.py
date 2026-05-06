#!/usr/bin/env python3
"""
Conan TCG Scraper
=================
Fetches card data from the official Takara Tomy site and outputs a JSON file
compatible with the Case File PWA at data/cards.json.

The site lazy-loads cards 100 at a time via AJAX. This script handles that by
calling the AJAX endpoint directly with pagination. It also probes for the
English image variants where they exist.

USAGE:
    pip install requests beautifulsoup4 lxml
    python scraper.py --out ../data/cards.json

OPTIONAL: Translate Japanese effect text using DeepL or Google Translate API.
    python scraper.py --translate deepl --deepl-key YOUR_KEY
    python scraper.py --translate google --google-key YOUR_KEY

Without translation, you'll get Japanese effect text + English structural data
(rarity, level, AP/LP, color, etc.). Card names are romanized where possible
using a small built-in dictionary; otherwise they remain Japanese.

Inspired by saitho's open-source crawler at
github.com/saitho/conantcg-english (do also consider just using their data!).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages missing. Install with:")
    print("    pip install requests beautifulsoup4 lxml")
    sys.exit(1)


BASE = "https://www.takaratomy.co.jp/products/conan-cardgame/"
LIST_URL = BASE + "cardlist/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ConanTcgTracker/1.0; personal use)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.7",
}

# Extend this with more characters as you go.
ROMAJI = {
    "江戸川コナン": "Conan Edogawa",
    "工藤新一": "Shinichi Kudo",
    "毛利蘭": "Ran Mouri",
    "毛利小五郎": "Kogoro Mouri",
    "服部平次": "Heiji Hattori",
    "遠山和葉": "Kazuha Toyama",
    "怪盗キッド": "Kaito Kid",
    "中森青子": "Aoko Nakamori",
    "赤井秀一": "Shuichi Akai",
    "世良真純": "Masumi Sera",
    "安室透": "Toru Amuro",
    "降谷零": "Rei Furuya",
    "灰原哀": "Ai Haibara",
    "阿笠博士": "Hiroshi Agasa",
    "ジン": "Gin",
    "ウォッカ": "Vodka",
    "ベルモット": "Vermouth",
    "工藤優作": "Yusaku Kudo",
    "工藤有希子": "Yukiko Kudo",
    "吉田歩美": "Ayumi Yoshida",
    "小嶋元太": "Genta Kojima",
    "円谷光彦": "Mitsuhiko Tsuburaya",
    # Add more as needed.
}

# Color/rarity/type mapping from Japanese to English
COLOR_MAP = {"青": "blue", "緑": "green", "白": "white", "赤": "red", "黄": "yellow", "黒": "black"}
TYPE_MAP = {"パートナー": "Partner", "キャラ": "Character", "イベント": "Event", "事件": "Case"}


def fetch_listing_page(session, package=None, page=1):
    """Fetch one paginated AJAX page from the cardlist endpoint."""
    params = {"page": page}
    if package:
        params["package"] = package
    url = LIST_URL
    r = session.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def discover_card_ids(html):
    """Pull card IDs out of the listing HTML.

    The site uses card IDs like CT-P01-001. We look in image alt attrs and
    data-* attrs to find them, since the markup is JS-driven.
    """
    soup = BeautifulSoup(html, "lxml")
    ids = []
    seen = set()
    # Look for elements with data-cardid or similar attrs
    for el in soup.select("[data-cardid], [data-card-id], [data-id]"):
        cid = el.get("data-cardid") or el.get("data-card-id") or el.get("data-id")
        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)
    # Fallback: look for /cardlist/?cardid= patterns in links
    for a in soup.select("a[href*='cardid=']"):
        m = re.search(r"cardid=([A-Z0-9\-]+)", a.get("href", ""))
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def fetch_card_detail(session, card_id):
    """Fetch the detail page for one card and parse fields."""
    url = LIST_URL + f"?cardid={card_id}"
    r = session.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # The card detail markup uses a definition-list-ish structure.
    # We collect labeled fields then map to English.
    fields = {}
    for dl in soup.select("dl, .card-detail, .card_info"):
        for dt in dl.select("dt"):
            label = dt.get_text(strip=True)
            dd = dt.find_next("dd")
            value = dd.get_text(" ", strip=True) if dd else ""
            fields[label] = value

    # Try to find the card image (Japanese version)
    img = soup.select_one("img.card-image, .card-image img, .card_pic img")
    image_url = urljoin(BASE, img["src"]) if img and img.get("src") else None
    image_id_match = re.search(r"/storage/card/([0-9a-f]+)\.(?:jpg|png)", image_url or "")
    image_id = image_id_match.group(1) if image_id_match else None

    # Probe for the English variant (sometimes available at /en/_cardimg/{id}.png)
    eng_img = None
    eng_candidate = f"{BASE}en/_cardimg/{card_id.split('-')[-1]}.png"
    try:
        h = session.head(eng_candidate, headers=HEADERS, timeout=10)
        if h.status_code == 200:
            eng_img = eng_candidate
    except Exception:
        pass

    # Map fields. Keys in `fields` are Japanese labels.
    name_ja = fields.get("カード名") or fields.get("名称") or ""
    name_en = ROMAJI.get(name_ja, name_ja)

    color_ja = fields.get("色", "")
    color = COLOR_MAP.get(color_ja, color_ja.lower() or None)

    type_ja = fields.get("カードの種類") or fields.get("種類", "")
    card_type = TYPE_MAP.get(type_ja, type_ja or None)

    rarity = fields.get("レアリティ") or None
    set_code = fields.get("収録先") or None

    def to_int(v):
        try: return int(re.sub(r"[^\d]", "", v or ""))
        except Exception: return None

    level = to_int(fields.get("レベル"))
    ap = to_int(fields.get("AP"))
    lp = to_int(fields.get("LP"))

    features_str = fields.get("特徴", "")
    features = [f.strip() for f in re.split(r"[、,/／]", features_str) if f.strip()]

    effect_ja = fields.get("カードの能力") or fields.get("能力") or ""

    illustrator = fields.get("イラストレーター") or None

    return {
        "id": card_id,
        "name": name_en,
        "nameJa": name_ja,
        "type": card_type,
        "color": color,
        "rarity": rarity,
        "level": level,
        "ap": ap,
        "lp": lp,
        "set": set_code,
        "features": features,
        "effect": effect_ja,    # still Japanese — translate in a separate pass
        "effectJa": effect_ja,
        "illustrator": illustrator,
        "imageId": image_id,
        "imageUrl": eng_img,    # only set if English variant exists
    }


def translate_with_deepl(text, key, target="EN-US"):
    if not text: return text
    r = requests.post(
        "https://api-free.deepl.com/v2/translate",
        headers={"Authorization": f"DeepL-Auth-Key {key}"},
        data={"text": text, "source_lang": "JA", "target_lang": target},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["translations"][0]["text"]


def translate_with_google(text, key, target="en"):
    if not text: return text
    r = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        params={"key": key},
        data={"q": text, "source": "ja", "target": target, "format": "text"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["data"]["translations"][0]["translatedText"]


def main():
    p = argparse.ArgumentParser(description="Scrape Conan TCG cards from the official site.")
    p.add_argument("--out", default="../data/cards.json", help="Output JSON path")
    p.add_argument("--package", help="Limit to a single package (e.g. CT-P09)")
    p.add_argument("--delay", type=float, default=0.6, help="Seconds between requests (be polite)")
    p.add_argument("--limit", type=int, help="Max cards to fetch (for testing)")
    p.add_argument("--translate", choices=["deepl", "google", "none"], default="none")
    p.add_argument("--deepl-key", help="DeepL API key (free tier ok)")
    p.add_argument("--google-key", help="Google Cloud Translate API key")
    p.add_argument("--existing", help="Path to existing cards.json to merge with (skip already-scraped)")
    args = p.parse_args()

    s = requests.Session()

    # Phase 1: discover all card IDs via the lazy-loaded listing
    print("Phase 1: Discovering card IDs...")
    card_ids = []
    page = 1
    while True:
        print(f"  Listing page {page}...", end=" ")
        try:
            html = fetch_listing_page(s, package=args.package, page=page)
        except Exception as e:
            print(f"failed: {e}")
            break
        new_ids = discover_card_ids(html)
        new_ids = [i for i in new_ids if i not in card_ids]
        print(f"found {len(new_ids)} new IDs")
        if not new_ids:
            break
        card_ids.extend(new_ids)
        page += 1
        time.sleep(args.delay)
        if args.limit and len(card_ids) >= args.limit:
            card_ids = card_ids[:args.limit]
            break

    print(f"Total card IDs: {len(card_ids)}")
    if not card_ids:
        print("No card IDs found. The site markup may have changed.")
        print("As a workaround, consider using saitho's data:")
        print("    https://github.com/saitho/conantcg-english")
        return

    # Skip already-scraped if --existing was given
    skip = set()
    existing_data = []
    if args.existing and Path(args.existing).exists():
        existing_data = json.loads(Path(args.existing).read_text(encoding="utf-8"))
        skip = {c["id"] for c in existing_data if c.get("effect") and c.get("name")}
        print(f"Will skip {len(skip)} cards already in {args.existing}")

    # Phase 2: fetch each card's detail
    print("Phase 2: Fetching card details...")
    cards = list(existing_data)
    for i, cid in enumerate(card_ids, 1):
        if cid in skip:
            continue
        print(f"  [{i}/{len(card_ids)}] {cid}...", end=" ")
        try:
            card = fetch_card_detail(s, cid)
            cards.append(card)
            print("ok")
        except Exception as e:
            print(f"failed: {e}")
        time.sleep(args.delay)

    # Phase 3: translate effects if requested
    if args.translate != "none":
        print(f"Phase 3: Translating effect text via {args.translate}...")
        for i, c in enumerate(cards, 1):
            if c.get("effect") and c["effect"] == c.get("effectJa") and c["effect"].strip():
                print(f"  [{i}/{len(cards)}] {c['id']}...", end=" ")
                try:
                    if args.translate == "deepl":
                        c["effect"] = translate_with_deepl(c["effect"], args.deepl_key)
                    elif args.translate == "google":
                        c["effect"] = translate_with_google(c["effect"], args.google_key)
                    print("ok")
                except Exception as e:
                    print(f"failed: {e}")
                time.sleep(0.2)

    # Save
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cards)} cards to {out}")


if __name__ == "__main__":
    main()
