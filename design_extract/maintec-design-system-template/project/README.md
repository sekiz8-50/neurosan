# Maintec — Design System

**Maintec — "The Future Techforce"** is a Dutch technical staffing / employment company
(part of **TecqGroep**, alongside sister brands **TecForce** and **TecqGroep**). Maintec
positions itself not as a temp agency (*uitzendbureau*) or secondment firm, but as an
**employer** — a collective of motivated technical specialists. Their core promise:
*"Continue inzetbaarheid van technisch talent. Voor vandaag en in de toekomst"*
(continuous availability & employability of technical talent, for today and the future).

Crucially: **their people are not "candidates" — they are colleagues** (*collega's*). The
entire brand voice speaks directly to skilled tradespeople as peers and future teammates.

This design system is bold, professional, and high-contrast — built on **orange, black, and
white**, dynamic real-world photography of tradespeople, and a heavy condensed display type.

---

## Brand context & sources

- **Maintec** — technical staffing, employer brand "The Future Techforce". Target audience:
  technical professionals & people (re)training into technical trades in the Netherlands.
- **TecqGroep** — parent group. Primary color deep blue `#182A49`.
- **TecForce** — sister brand. Primary color sky blue `#8AADC7`.
- Maintec's distinguishing color is **Orange (Mango Tango) `#FF7D2F`**.

**Provided source materials** (in `uploads/`):
- `Branding Guide Maintec.pdf` — 15-page brand guide v1.2 (01/2023), by Campus Werkspoor.
  Covers merkverhaal, propositie, kleurgebruik, concept, social, fotografie, typografie, logo.
- `Kleurenkaart TecqGroep, TecForce en Maintec.xlsx` — color sheet for all three brands.
- Fonts: `Rift Bold.otf`, `Transducer Regular.otf`, `exljbris - MuseoSans-900.otf`.
- Logos: `Logo_Maintec*.svg` (standard, DIAP/reversed, wit_zwart, zwart_wit). Note: the
  source EPS files referenced in the brief were **not** delivered — only the SVGs.

> The raw source SVGs reference `.st0`/`.st1` CSS classes with **no fill definitions**, so
> they render as solid black out of the box. Cleaned, correctly-colored standalone versions
> live in `assets/logo-maintec-*.svg` — **use those**.

---

## CONTENT FUNDAMENTALS — voice & tone

**Language:** Primary copy is **Dutch**. The tagline and signature lines are English:
*"Join the Future Techforce"*, *"The Future Techforce"*.

**Person & address:** Speaks in **first-person plural ("Wij / We")** as the employer, and
addresses the reader directly as **"je / jij"** (informal "you"). Warm, direct, peer-to-peer —
they literally open ads with **"HALLO COLLEGA"** (hello colleague).

**Tone:** Bold, confident, optimistic, and human. Ambitious but down-to-earth (*nuchter*).
The brand character words from the guide: *Enthousiast · Saamhorig · Nuchter · Zorgzaam ·
Zorgvuldig · Ondernemend · Bevlogen · Benaderbaar* (enthusiastic, together, level-headed,
caring, careful, enterprising, passionate, approachable).

**Casing:** Display headlines are **ALL CAPS** (Rift). Body is sentence case. The tagline
emphasizes the last word in orange: JOIN THE FUTURE **TECHFORCE**.

**Emoji:** **Not used.** Keep it clean and professional.

**Vocabulary rules:**
- ✅ "collega" (colleague), "vakspecialist / vakprofessional", "werkgever" (employer),
  "in dienst" (employed by us), "samen" (together), "techniek".
- 🚫 Avoid "kandidaat" (candidate), "uitzendbureau" (temp agency), "detacheerder".
  The whole point is they are an *employer*, not an agency.

**Example copy (verbatim from guide):**
- *"HALLO COLLEGA"*
- *"Wij zijn een collectief van gemotiveerde vakprofessionals binnen de technische sector."*
- *"Zie ons niet als het zoveelste uitzendbureau... Wij zijn op de eerste plaats werkgever.
  Onze mensen zijn geen 'kandidaten'. Ze zijn collega's."*
- *"Laten we samen onze krachten bundelen."*
- *"Join our Future Techforce."*

---

## VISUAL FOUNDATIONS

**Colors** — three brand colors do almost all the work:
- **Orange / Mango Tango `#FF7D2F`** — the single accent. Used for highlight words,
  buttons, the bracket device, and emphasis. Never dilute with other accent hues.
- **Black `#000000`** — the signature surface. Most hero compositions sit on black.
- **White `#FFFFFF`** — clean text & light surfaces.
- **Dim Gray `#69696A`** — the only support neutral defined by the brand.
- Full ramps (orange + warm neutral) are derived in `colors_and_type.css`.

**Typography** — three roles, clear hierarchy:
- **Rift Bold** → big display headlines, **CAPITALS ONLY**. Condensed, athletic, powerful.
- **Transducer Regular** → body copy and subheads.
- **Museo Sans 900** → the logo wordmark **only**. Never for headlines/body.

**Backgrounds:** Predominantly **solid black or solid white** — no gradients, no patterns,
no textures. Drama comes from full-bleed photography against black, not from decorative
backgrounds. When photos are used they often run full-bleed with a black bar or scrim
carrying the headline.

**Photography** (the heart of the concept): dynamic, realistic *working moments* shot from
a **low camera angle** to keep tension and make the viewer feel close. Two genres:
*"aan het werk"* (two real tradespeople working together — collaboration is mandatory, never
a lone individual; the second person sits slightly soft in the background) and *"groepsfoto"*
(a powerful, dynamic mix of professionals + consultants). Bright, clean, real environments,
full-color — a deliberate rejection of the dark, cold imagery common in the technical sector.
Official photo set lives in `assets/imagery/*.jpg`.

**Animation:** Social uses a **zoom-in on the main subject** ("hoofdrolspeler"), supported by
the same ad copy. Motion is purposeful and punchy — no bouncy/playful easing. Favor confident
fades and slow pushes; let the photography and bold type carry the energy.

**Hover / press states:** Buttons darken on hover (`orange-500 → orange-600`) and deepen
further on press (`→ orange-700`). Keep it tactile and simple; avoid scale-bounce gimmicks.

**Borders & corners:** The brand is **angular and tight**. Default radius `4px` for buttons/
inputs, `8px` for cards, `0` for full-bleed bands. Use strong black 1.5px borders for outline
buttons and emphasis frames.

**Shadows:** Restrained, low-spread (see Elevation tokens). On black surfaces, separate with
hairline borders (`rgba(255,255,255,.1)`) rather than shadows.

**The bracket device `[ ]`:** Orange brackets frame the tagline and double as a standalone
corner mark / callout device. It's the brand's most flexible graphic asset besides the logo.

**Transparency & blur:** Used sparingly — black scrims/gradients over photography so headline
text stays legible. Avoid frosted-glass / heavy blur effects.

**Layout rules:** Big headline, generous black space, one orange accent per view, logo
top-left, tagline bottom. High contrast, confident, never cluttered.

---

## ICONOGRAPHY

The brand guide defines **no proprietary icon set or icon font** — the visual language is
carried by **photography, the wordmark, and the orange bracket device**, not by iconography.

Guidance for building Maintec interfaces:
- **No emoji.** Ever.
- Keep icons **minimal, line-based, and functional** — they should never compete with the
  photography or the orange accent.
- Recommended substitute set: **[Lucide](https://lucide.dev)** (CDN), `stroke-width: 2`,
  square caps. It matches the brand's clean, angular, no-nonsense character. This is a
  **substitution** — flag to the client if they later supply an official icon set.
- The orange **`[ ]` bracket** is the closest thing to a brand "icon" — use it as a marker,
  bullet, or corner device.

Assets copied into `assets/`:
- `logo-maintec-black.svg` — primary (light bg)
- `logo-maintec-white.svg` — reversed (dark bg)
- `logo-maintec-mono-black.svg` / `logo-maintec-mono-white.svg` — single-color
- `logo-maintec-orange.svg` — all-orange
- `imagery/*.jpg` — **official hi-res Maintec photography** (16 images: technicians at work
  in branded workwear + team/group shots). Use these directly: `worker-duct-install`,
  `workers-pipes-trio`, `workers-electrical-panel`, `worker-laptop-hallway`,
  `worker-smiling-laptop`, `team-seated`, `team-group-large`, `team-beams`, `team-hall`,
  `team-scaffolding`, `team-toolbox`, `welder-hull`, `welder-sparks`, `crane-operator`,
  `workers-blueprint`, `workers-shipbuild`.

---

## INDEX — what's in this system

| Path | What |
|---|---|
| `README.md` | This file — brand context, voice, visual foundations, iconography |
| `colors_and_type.css` | All design tokens: color, type, spacing, radii, shadows + semantic classes |
| `SKILL.md` | Agent-skill entry point (Claude Code compatible) |
| `fonts/` | Rift Bold, Transducer Regular, Museo Sans 900 |
| `assets/` | Cleaned logos (5 variants) + sample photography |
| `preview/` | Design-system specimen cards (rendered in the Design System tab) |
| `ui_kits/website/` | Maintec employer/recruitment **website** UI kit (React/JSX) |

### UI Kits
- **`ui_kits/website/`** — the Maintec recruitment site: hero, vacancy listings, vacancy
  detail, story section, footer. See its own `README.md`.

*(No slide template was provided in the source materials, so no slide deck templates are
included. Ask if you'd like branded deck templates built from the same foundations.)*

---

*Brand guide authored by Campus Werkspoor. This design system is a working reconstruction for
design tooling — verify against official brand assets before production use.*
