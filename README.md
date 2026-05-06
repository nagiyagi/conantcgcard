# Case File · Conan TCG Tracker

A personal, offline-first PWA for tracking Detective Conan TCG card collection and building decks.

> **Status:** Working PWA shell with 30 sample cards. Data acquisition is the part you'll need to choose a path on — see [Getting full card data](#getting-full-card-data).

## Features

- **Browse** all cards with search by name/ID/effect text and filter by color, type, rarity, set
- **Collections** — track which cards you actually own, with quantities
- **Decks** — build decks with stats (color balance, level curve, type breakdown), export as text
- **Offline** — service worker caches the app shell + card data + card images on demand
- **Installable** — drop to home screen on iOS/Android, install as app on desktop
- **Backup/restore** — export everything to a single JSON file
- **No accounts, no tracking, no servers** — all data lives in your browser's IndexedDB


## Running it

### Option 1: GitHub Pages (easiest, free, gets you HTTPS for full PWA support)

1. Create a new GitHub repository.
2. Push these files to it.
3. Settings → Pages → Source: `main` branch, root.
4. Open `https://<your-username>.github.io/<repo-name>/`.
5. On Chrome/Edge: install via the address bar icon. On iOS Safari: Share → Add to Home Screen.

### Option 2: Netlify / Vercel / Cloudflare Pages

Drag-and-drop the folder. Done.

### Option 3: Local dev (no install needed)

```bash
cd conan-tracker
python3 -m http.server 8000
# open http://localhost:8000
```

> **Note:** Service workers require either `localhost` or HTTPS. Don't open `index.html` via `file://` — it'll mostly work but offline support won't.

## Getting full card data

The Takara Tomy site has 2,000+ cards but lazy-loads them and presents them in Japanese. You have three reasonable paths:

### Path A: Reuse community data (fastest, recommended)

Two community projects have already done the hard work of cataloging and translating cards:

- **[saitho/conantcg-english](https://github.com/saitho/conantcg-english)** — open-source, fan-translated. Powers [conan-tcg.net](https://conan-tcg.net).
- **[Conan TCG App](https://conan-tcg-app.com)** - open-source.
- **[LastStand Conan TCG List](https://laststand.co.th/conan_cards)** - open-source, fan-translated Thai version.
If you go this route: clone or fork their data, transform it into the schema this PWA expects (see "Card schema" below), drop the result at `data/cards.json`, and you're done.

**Please attribute properly** if you use community data. All projects are explicit about being fan resources.

### Path B: Run the bundled scraper

```bash
cd conan-tracker/tools
pip install requests beautifulsoup4 lxml
python scraper.py --out ../data/cards.json --delay 1.0
```

The scraper:

1. Walks the official site's lazy-loaded listing pages (handles pagination automatically)
2. Fetches each card's detail page
3. Extracts structured fields (rarity, level, AP/LP, color, type, features)
4. Probes for English image variants where available
5. Returns Japanese effect text by default

To translate effect text, add API credentials:

```bash
# DeepL (free tier: 500k chars/month — enough for all 2k cards)
python scraper.py --translate deepl --deepl-key YOUR_KEY

# Or Google Cloud Translate
python scraper.py --translate google --google-key YOUR_KEY
```

> **Caveat:** The site's exact markup wasn't fully reverse-engineered — you may need to adjust the CSS selectors in `discover_card_ids()` and `fetch_card_detail()` if the script returns 0 results. The AJAX endpoint for pagination may also be different from the listing URL; inspect Network tab in DevTools to find it. A working version of this scraping logic exists in saitho's repo (`crawler/` folder) — that's a good reference if you need to debug.

### Path C: Add cards manually as you collect them

Open Settings → Import cards.json after editing the file by hand. Use the sample cards in `data/cards.json` as a template. This is fine if you just want to track a few starter decks.

## Card schema

Each card in `data/cards.json` is an object with these fields. Only `id` is strictly required; everything else is optional but recommended.

```jsonc
{
  "id": "CT-P01-001",              // Required, unique
  "nameJa": "江戸川コナン",         // Japanese name (for search)
  "type": "Partner",               // Partner | Character | Event | Case
  "color": "blue",                 // blue|green|white|red|yellow|black
  "rarity": "RP",                  // C | CP | R | RP | SR | SRP | SEC | MR | etc.
  "level": 1,                      // 1-9, or null for events/cases without
  "ap": 1000,                      // Attack Power, integer or null
  "lp": 2,                         // Life Points, integer or null
  "set": "CT-P01",                 // Set code
  "features": ["Detective", "..."], // Array of features (strings)
  "effect": "[Cut-In] When ...",   // English effect text
  "illustrator": "Gosho Aoyama",
  "imageId": "1714012985492767",   // Image ID on takaratomy.co.jp/storage/card/
  "imageUrl": null                 // Optional override for direct URL
}
```

The PWA constructs image URLs from `imageId` like:
`https://www.takaratomy.co.jp/products/conan-cardgame/storage/card/{imageId}.jpg`

Or it uses `imageUrl` directly if you provide one (useful for the English variants at `/en/_cardimg/`).

## Storage & limits

- **IndexedDB** holds cards, collections, and decks. Browsers typically allow hundreds of MB to a few GB per origin.
- **Cache API** holds the app shell, card data JSON, and card images viewed during your session. Images load and cache lazily — pre-fetching all 2,000 would be ~150MB.
- **No quotas hit in practice** unless you cache every image, which the app doesn't do by default.

To see what's stored: DevTools → Application → IndexedDB / Cache Storage.

## Development notes

- Pure HTML/CSS/JS, no build step, no framework. ~1500 lines total in `index.html`.
- Self-contained tagged template literals (`html` and `raw`) for safe rendering with auto-escaping.
- IndexedDB wrapped in 30 lines of promise helpers.
- Service worker uses a cache-first strategy for shell + images, network-first for card data (so updates propagate when online).

## Aesthetic

Detective noir / case file. Dark navy background, crimson accents, serif headers (Playfair Display), monospace data fields (JetBrains Mono). The "CONFIDENTIAL · TCG" stamp in the header is the signature touch.

If you'd prefer a brighter look: edit the CSS variables under `:root` in `index.html`. Pull `--bg`, `--bg-soft`, `--ink` toward light values and the rest follows.

## License & attribution

This is a fan tool. Detective Conan © Gosho Aoyama / Shogakukan. Detective Conan TCG © TOMY. Card images and content remain the property of their respective owners. No commercial use intended.

The PWA code itself is yours to do whatever you want with — call it MIT or public domain.
