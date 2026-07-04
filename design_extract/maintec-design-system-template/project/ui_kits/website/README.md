# Maintec — Website UI Kit

A high-fidelity recreation of the **Maintec employer / recruitment website**, built directly
from the brand guide's visual language (the *"HALLO COLLEGA"* ad concept: bold Rift headlines,
orange accent, black surfaces, dynamic low-angle tradesperson photography).

> **Source note:** No live site or codebase was provided — only the brand guide PDF. This kit
> reconstructs the brand's design language faithfully but does **not** copy a specific existing
> page. Verify against the real maintec.nl before production use.

## Run
Open `index.html`. It's an interactive click-through prototype:
- **Home** → hero (HALLO COLLEGA), brand manifesto, vacancy grid with filters, employer CTA band, footer.
- Click any **vacancy card** → vacancy detail page with an inline apply form → submit shows a
  "Welkom collega!" confirmation.
- **Terug naar vacatures** returns home.

## Files
| File | Contents |
|---|---|
| `index.html` | App shell — loads React 18 + Babel + Lucide + all component scripts |
| `components.jsx` | Primitives: `Icon` (Lucide), `Logo`, `Button`, `Tag`, `Bracket`, `Eyebrow` |
| `Chrome.jsx` | `Header` (transparent-over-hero → solid on scroll), `Footer` |
| `Home.jsx` | `Hero`, `Manifesto`, `Vacancies` + `VacancyCard`, `EmployerBand`, `VACANCIES` data |
| `VacancyDetail.jsx` | `VacancyDetail` — detail hero + content + sticky apply card |
| `app.jsx` | `App` — route state (home ↔ vacancy), scroll handling |

## Design notes
- **Type:** Rift Bold (display, ALL CAPS), Transducer (body) — pulled from `../../colors_and_type.css`.
- **Color:** one orange accent (`--orange-500`) per view; black + white do the rest.
- **Icons:** Lucide (CDN, stroke 2) — a documented substitute; swap if Maintec supplies a set.
- **Buttons:** uppercase, tight 4px radius, darken on hover.
- **Imagery:** official hi-res Maintec photography from `../../assets/imagery/*.jpg`.

## Components worth reusing
`Button` (primary/dark/light/outline/ghost), `Tag` (orange/dark/soft/out), `VacancyCard`,
the sticky `Header`, the dark `Footer` with bracket device, and the apply-form pattern.
