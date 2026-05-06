# Detective Conan TCG · Case File

A mobile-first PWA for browsing, searching, and tracking your Detective Conan TCG card collection offline. Pulls data from [laststand.co.th/conan_cards](https://laststand.co.th/conan_cards) and stores everything locally on your device.

## Features

- **Browse** all cards in a responsive grid (3 cols mobile → 7 cols desktop) with card code (e.g. `P001`) and name overlay on each tile
- **Bilingual search** by name, traits, or set in **Thai *or* English** — type `Conan` or `โคนัน`, both work. A built-in Detective Conan character + trait dictionary aliases ~150 common Thai terms to English so search just works without any extra setup.
- **Search** also matches card code, set ID, type, color, rarity, and database `№`
- **Filter** by status (All / In Evidence / Outstanding) and by type (Partner / Character / Event / Case)
- **Bilingual card detail** — modal shows the Thai name with the English translation as a secondary line; traits show both languages side-by-side
- **Mark as owned** with a tap — owned state persists locally
- **Resync** the card list from the source site with one tap (auto + CORS proxy + manual fallback)
- **Fetch card details** for every card — name, code, type, rarity, colors, origin, AP/LP, ability text — pulled from the `cc_info` endpoint, cached locally
- **Cache all card images** for true offline browsing
- **Installable** as a real app on iOS / Android home screen
- **Backup** — export & import your collection as JSON
- 312 cards seeded inline; resync pulls the full latest set

## Files

| File | Purpose |
|---|---|
| `index.html` | The app (HTML + CSS + JS, all inline, ~55 KB) |
| `manifest.webmanifest` | PWA manifest |
| `sw.js` | Service worker — offline app shell & image caching |
| `icon-192.png`, `icon-512.png`, `icon-512-maskable.png` | App icons |
| `apple-touch-icon.png` | iOS home screen icon |
| `favicon-32.png` | Browser tab icon |
| `cards.json` | Standalone seed data (also embedded in `index.html`) |

## Installing on your phone

**Android / Chrome:** the app shows an Install banner after a few visits, or use the browser menu → "Install app".

**iOS / Safari:** tap the Share button → "Add to Home Screen". (iOS doesn't support the install banner spec yet, but the manifest still configures the icon, name, and standalone display mode.)

## Resync — how it works

The app's source of truth is two endpoints:

```
List     /cc_search?query=&card_type=&...      (returns img tags with src + data-card-id)
Detail   /cc_info?cardId={id}&query=&...        (returns one card's full JSON)
```

Two separate sync actions:

**Auto-Sync now** — pulls the *list* of cards (image hash + database id). Fast, one HTTP request, ~16 KB. Tries direct fetch → public CORS proxies (`api.allorigins.win`, `corsproxy.io`) → manual paste fallback.

**Fetch all details** — pulls each card's name, code (e.g. `P001`), type, rarity, colors, origin, AP/LP, ability text. ~300+ small HTTP requests, throttled to 4 in-flight at a time, takes 30–90 seconds. Goes through the same proxy chain. Progress is shown live and saved every ~1.5 s so a closed tab doesn't lose work.

After every sync the app:
- Stores the new card list in `localStorage`
- Stamps `localStorage["conan.lastSync.v1"]` with the timestamp
- Preserves your owned-state and any already-fetched details

The card-detail data unlocks **search by name** (Thai or English partial match), **search by card code** (`P001`, `B01001P`), and the **type filter row** (which only appears once at least one card has a `type` field).

## Cache images for offline

In Sync & Settings → "Download all card images". This sends every image URL to the service worker, which caches them with `cache: 'no-cors'` (the response is opaque but cacheable). Once warmed, the case file works fully offline. Expected size: 30–80 MB depending on how many cards are in the current set.

## Storage layout

| Key | Type | Purpose |
|---|---|---|
| `conan.cards.v1` | JSON `[{h,id,code?,name?,type?,...},…]` | Latest card list (with details if fetched) |
| `conan.owned.v1` | `{id:1,…}` JSON | Set of owned card IDs |
| `conan.lastSync.v1` | ISO date string | Last successful list sync |
| `conan.lastDetail.v1` | ISO date string | Last successful detail-fetch run |
| `conan.dismissInstall.v1` | `'1'` | User dismissed the install banner |
| Cache `*-shell` | Cache API | Pre-cached app shell (HTML/CSS/JS/icons) |
| Cache `*-images` | Cache API | Card images (cached on demand or via warm) |
| Cache `*-runtime` | Cache API | Other runtime fetches (Google Fonts, etc.) |

The app handles legacy storage formats gracefully — if you had a previous build with the compact `[[hash, id], …]` shape, it'll auto-migrate the first time the app loads.

## Notes & caveats

- Card metadata: only `image hash` and `card_id` are exposed by the search endpoint. Card names, types, colors, and rarities aren't included in the JSON, so search is by card number. If the source site adds metadata to its API later, the parser in `index.html` (function `parseCards`) is the place to extend.
- This app does not display ads or send any analytics.
- Card images are served from `laststand.co.th`. The service worker caches them after first load, but the first load needs network.
- Card art © 青山剛昌／小学館 © TOMY. Thai reference translations are by laststand.co.th — not the official TAKARA TOMY translation.
- This app is a personal collection tracker. It is not affiliated with TAKARA TOMY, Shogakukan, or laststand.co.th.

## Two-tier translation

The app reaches your search query in two layers, so you can type in either Thai or English without setup:

1. **Built-in dictionary** (instant, offline). The `TH_EN_DICT` constant near the top of the script aliases ~150 Detective Conan-specific terms to English — main characters (Conan, Shinichi, Ran, Heiji, Kid, Akai, Amuro, Haibara, the whole Black Org codename roster, Detective Boys, etc.), the trait categories from the source's filter list (Detective, Police, Hokkaido Police, Ramen Shop, Detective Agency, etc.), and the core game-system terms (Investigation Phase, Sleep, Assist, etc.). This handles the common case without any network call.

2. **Online MyMemory pass** (optional, one-time per card). For one-off NPCs, locations, set names, or anything else the dictionary doesn't cover, Sync & Settings → "Translate remaining names" runs each Thai name through the free [MyMemory API](https://mymemory.translated.net) and caches the result in `card.nameEn`. Throttled to 3 in-flight requests with gentle pacing, persists every ~1.5 s. The status line shows how many cards still need translation; the button disables itself when nothing remains. Free tier is ~50K chars/day per IP, plenty for the full ~300-card list with traits.

Search matches against everything: original Thai + dictionary translation + MyMemory translation + structured fields (code, set ID, type, color, rarity, origin, traits). The empty state is also diagnostic — if a search returns nothing and most cards lack details or English aliases, it tells you exactly which sync step to run next.

## Customizing

- **Look and feel:** all CSS is in the `<style>` block in `index.html`. Color tokens are CSS custom properties at the top of `:root`.
- **Filters / sort:** the `getVisibleCards()` function in the script block is a small pure function — easy to extend for new filters.
- **Translation dictionary:** the `TH_EN_DICT` constant near the top of the script holds the Thai → English aliases that power bilingual search and modal display. Roughly 150 entries covering main Detective Conan characters (Conan, Shinichi, Ran, Kogoro, Heiji, Kid, Akai, Amuro, Haibara, etc.), the trait categories from the source site's filter list (Detective, Police, Black Organization, the Detective Boys, prefectural police forces, professions, etc.), and core game terms (Investigation Phase, Sleep, Assist, etc.). Keys are sorted longest-first so multi-word phrases are matched before their components, which means `เอโดงาวะ โคนัน` resolves to `Edogawa Conan` rather than `Edogawa` + `Conan` separately. Add more entries to extend coverage; typos and contributions welcome.
- **Image cache strategy:** `sw.js` is straightforward, with cache-first for images and network-first for the search endpoint. Tweak as needed.

## Browser support

- Chrome / Edge / Samsung Internet (Android): full PWA support, install prompt, offline.
- Safari (iOS 16+): "Add to Home Screen" works; service worker caches; no install prompt UI.
- Firefox (Android): works but no install prompt.
- Desktop browsers: works as a regular web app; install support varies.
