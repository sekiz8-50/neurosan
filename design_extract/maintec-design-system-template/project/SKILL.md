---
name: maintec-design
description: Use this skill to generate well-branded interfaces and assets for Maintec ("The Future Techforce"), a bold Dutch technical staffing agency, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and
create static HTML files for the user to view. If working on production code, you can copy
assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or
design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_
production code, depending on the need.

## Quick reference
- **Brand:** Maintec — "The Future Techforce". A collective of technical specialists; an
  *employer*, not a temp agency. People are **collega's** (colleagues), never "candidates".
- **Colors:** Orange/Mango Tango `#FF7D2F` (the one accent) · Black `#000000` · White ·
  Dim Gray `#69696A`. Full tokens in `colors_and_type.css`.
- **Type:** Rift Bold (display, **ALL CAPS only**) · Transducer Regular (body/subheads) ·
  Museo Sans 900 (logo wordmark only). Fonts self-hosted in `fonts/`.
- **Voice:** Dutch primary, English taglines ("Join the Future Techforce"). Direct, warm,
  peer-to-peer, confident. No emoji.
- **Look:** black surfaces, big orange-accented Rift headlines, warm low-angle photography of
  tradespeople working *together*, the orange `[ ]` bracket device. Tight corners, restrained
  shadows, one orange accent per view.
- **Logos:** `assets/logo-maintec-{black,white,mono-black,mono-white,orange}.svg`.
- **UI components:** `ui_kits/website/` (React/JSX) — Header, Footer, Button, Tag, VacancyCard,
  apply form, hero patterns.

Always pull tokens and fonts from `colors_and_type.css`. Substitute Lucide icons (stroke 2).
