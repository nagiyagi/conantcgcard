#!/usr/bin/env python3
"""
conan-tcg-app.com Data Converter
================================
Converts a card data dump from conan-tcg-app.com (the unofficial Conan TCG
support app by @will_conan_tcg) into the format used by this PWA's
data/cards.json.

USAGE
-----
1. Open conan-tcg-app.com in Chrome and open DevTools (F12).
2. Find the request in the Network tab whose response is the card list JSON.
3. Save that response to a local file. Easiest method: click the request,
   open the Response tab, Ctrl+A inside the response, Ctrl+C, paste into a
   new text file (e.g., `raw.json`).
4. Run:
       python convert_conantcg_app.py --input raw.json --out ../data/cards.json

The converter accepts either a top-level JSON array of cards, or any wrapper
object containing one (e.g. {"data": [...]}, {"cards": [...]}).

ATTRIBUTION
-----------
Card data sourced from conan-tcg-app.com — please consider supporting the
developer at https://will-app.fanbox.cc if you rely on their work.
"""

import argparse
import json
import re
import sys
from pathlib import Path


# Known character name romanizations. Falls back to Japanese for everyone else.
ROMAJI = {
    "江戸川コナン":     "Conan Edogawa",
    "工藤新一":         "Shinichi Kudo",
    "毛利蘭":           "Ran Mouri",
    "毛利小五郎":       "Kogoro Mouri",
    "服部平次":         "Heiji Hattori",
    "遠山和葉":         "Kazuha Toyama",
    "怪盗キッド":       "Kaito Kid",
    "黒羽快斗":         "Kaito Kuroba",
    "中森青子":         "Aoko Nakamori",
    "赤井秀一":         "Shuichi Akai",
    "世良真純":         "Masumi Sera",
    "安室透":           "Toru Amuro",
    "降谷零":           "Rei Furuya",
    "灰原哀":           "Ai Haibara",
    "宮野志保":         "Shiho Miyano",
    "阿笠博士":         "Hiroshi Agasa",
    "ジン":             "Gin",
    "ウォッカ":         "Vodka",
    "ベルモット":       "Vermouth",
    "工藤優作":         "Yusaku Kudo",
    "工藤有希子":       "Yukiko Kudo",
    "吉田歩美":         "Ayumi Yoshida",
    "小嶋元太":         "Genta Kojima",
    "円谷光彦":         "Mitsuhiko Tsuburaya",
    "鈴木園子":         "Sonoko Suzuki",
    "目暮十三":         "Juzo Megure",
    "高木渉":           "Wataru Takagi",
    "佐藤美和子":       "Miwako Sato",
    "白鳥任三郎":       "Ninzaburo Shiratori",
    "千葉和伸":         "Kazunobu Chiba",
    "山村ミサオ":       "Misao Yamamura",
    "大和敢助":         "Kansuke Yamato",
    "上原由衣":         "Yui Uehara",
    "諸伏景光":         "Hiromitsu Morofushi",
    "諸伏高明":         "Takaaki Morofushi",
    "松田陣平":         "Jinpei Matsuda",
    "萩原研二":         "Kenji Hagiwara",
    "伊達航":           "Wataru Date",
    "ジョディ・スターリング": "Jodie Starling",
    "ジェイムズ・ブラック": "James Black",
    "アンドレ・キャメル": "Andre Camel",
    "本堂瑛祐":         "Eisuke Hondou",
    "本堂瑛海":         "Hidemi Hondou",
    "水無怜奈":         "Rena Mizunashi",
    "キャンティ":       "Chianti",
    "コルン":           "Korn",
    "キール":           "Kir",
    "ライ":             "Rye",
    "バーボン":         "Bourbon",
    "スコッチ":         "Scotch",
    "ピスコ":           "Pisco",
    "テキーラ":         "Tequila",
    "シェリー":         "Sherry",
    "宮本由美":         "Yumi Miyamoto",
    "新出智明":         "Tomoaki Araide",
    "森谷帝二":         "Teiji Moriya",
    "沖矢昴":           "Subaru Okiya",
    "羽田秀吉":         "Shukichi Haneda",
    "宮本伊織":         "Iori Muga",
    "脇田兼則":         "Kanenori Wakita",
    "毛利英理":         "Eri Kisaki",
    "妃英理":           "Eri Kisaki",
    "工藤新一(高校生)": "Shinichi Kudo (High School)",
}

TYPE_MAP = {
    "パートナー":  "Partner",
    "キャラ":      "Character",
    "イベント":    "Event",
    "事件":        "Case",
}

COLOR_MAP = {
    "青": "blue",
    "緑": "green",
    "白": "white",
    "赤": "red",
    "黄": "yellow",
    "黒": "black",
}


def derive_set(card_num):
    """
    Extract a set code from card_num.

    Examples:
        "PR287"        -> "PR"
        "P01-001"      -> "P01"
        "CT-P01-001"   -> "CT-P01"
        "D11-040"      -> "D11"
    """
    if not card_num:
        return None
    s = str(card_num).strip()
    # If hyphenated and the last segment is digits, the set is everything before.
    if "-" in s:
        head, tail = s.rsplit("-", 1)
        if tail.isdigit():
            return head
    # Otherwise, strip trailing digits to get the alphabetic prefix.
    stripped = re.sub(r"\d+$", "", s)
    return stripped or s


def combine_abilities(src):
    """
    The source splits abilities into separate fields. We concatenate them with
    blank lines, preserving each ability's built-in 【...】 label.
    """
    parts = []
    for key in ("disguise", "cut_in", "hirameki", "feature", "difficulty_txt"):
        v = src.get(key)
        if v and str(v).strip():
            parts.append(str(v).strip())
    return "\n\n".join(parts)


def normalize_features(s):
    """Split comma-separated category string into a list."""
    if not s:
        return []
    if isinstance(s, list):
        return [str(t).strip() for t in s if str(t).strip()]
    # Source uses "," but Japanese sometimes uses "、" or "/"
    parts = re.split(r"[,、/／]", str(s))
    return [p.strip() for p in parts if p.strip()]


def to_int(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(v)
    digits = re.sub(r"[^\d-]", "", str(v))
    try:
        return int(digits)
    except ValueError:
        return None


def convert_card(src):
    """Map one source card dict to our PWA's schema."""
    name_ja = (src.get("name") or "").strip()
    name_en = ROMAJI.get(name_ja, name_ja)

    return {
        "id":          src.get("card_num") or src.get("card_id"),
        "name":        name_en,
        "nameJa":      name_ja,
        "kana":        src.get("kana"),
        "type":        TYPE_MAP.get(src.get("type", ""), src.get("type")),
        "color":       COLOR_MAP.get(src.get("color", ""), src.get("color")),
        "rarity":      src.get("rarity"),
        "level":       to_int(src.get("cost")),
        "ap":          to_int(src.get("ap")),
        "lp":          to_int(src.get("lp")),
        "set":         derive_set(src.get("card_num", "")),
        "features":    normalize_features(src.get("category")),
        "effect":      combine_abilities(src),
        "effectJa":    combine_abilities(src),
        "illustrator": src.get("illustrator"),
        "imageUrl":    src.get("img_url"),
        # Extra fields preserved for possible future PWA enhancements:
        "direction":   src.get("direction"),
        "isKira":      src.get("is_kira"),
    }


def extract_records(data):
    """Find the card array inside whatever wrapper structure was used."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Try common envelope keys.
        for key in ("cards", "data", "items", "results", "list", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # Maybe nested one level deeper.
        for v in data.values():
            if isinstance(v, dict):
                for key in ("cards", "data", "items", "results", "list"):
                    if key in v and isinstance(v[key], list):
                        return v[key]
            elif isinstance(v, list) and v and isinstance(v[0], dict) and "card_num" in v[0]:
                return v
    return []


def main():
    ap = argparse.ArgumentParser(
        description="Convert conan-tcg-app.com card data to the PWA cards.json format."
    )
    ap.add_argument("--input", required=True, type=Path,
                    help="Path to the raw JSON response file from conan-tcg-app.com")
    ap.add_argument("--out", type=Path, default=Path("../data/cards.json"),
                    help="Output path (default: ../data/cards.json)")
    ap.add_argument("--peek", action="store_true",
                    help="Print one converted card and exit (don't write output)")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    try:
        with args.input.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Failed to parse {args.input}: {e}", file=sys.stderr)
        print("Make sure the file contains the raw JSON response, not the HTML page.",
              file=sys.stderr)
        sys.exit(1)

    records = extract_records(data)
    if not records:
        print("No card records found in the input file.", file=sys.stderr)
        print(f"Top-level type: {type(data).__name__}", file=sys.stderr)
        if isinstance(data, dict):
            print(f"Top-level keys: {list(data.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(records)} card record(s) in {args.input}")

    converted = []
    seen_ids = set()
    skipped = 0
    for src in records:
        if not isinstance(src, dict):
            skipped += 1
            continue
        card = convert_card(src)
        if not card["id"]:
            skipped += 1
            continue
        if card["id"] in seen_ids:
            continue
        seen_ids.add(card["id"])
        converted.append(card)

    # Sort by set, then by id within set.
    converted.sort(key=lambda c: (c.get("set") or "", c.get("id") or ""))

    if args.peek:
        print("\nSample converted card:")
        print(json.dumps(converted[0], ensure_ascii=False, indent=2))
        print(f"\n(Would write {len(converted)} cards to {args.out})")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)

    # Summary by set.
    set_counts = {}
    for c in converted:
        set_counts[c.get("set") or "?"] = set_counts.get(c.get("set") or "?", 0) + 1

    print(f"\n✓ Wrote {len(converted)} cards to {args.out}")
    if skipped:
        print(f"  Skipped {skipped} record(s) (no ID or invalid format)")
    print("\nCards per set:")
    for s, n in sorted(set_counts.items()):
        print(f"  {s:12} {n:>5}")
    translated = sum(1 for c in converted if c["name"] != c["nameJa"])
    print(f"\nNames romanized: {translated} / {len(converted)} "
          f"(rest kept Japanese — extend ROMAJI dict in this script to add more)")


if __name__ == "__main__":
    main()
