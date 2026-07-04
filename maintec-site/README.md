# Maintec — The Future Techforce (website)

A self-contained recruitment website implementing the **Maintec design system**
(orange `#FF7D2F` / black / white, Rift display headlines, Transducer body, the
orange `[ ]` bracket device, low-angle tradesperson photography).

Built from the Claude Design handoff bundle — no build step, no framework runtime.
Plain HTML + CSS + vanilla JS. Fonts, images and logos are self-hosted; only the
Lucide icon set loads from CDN (the brand guide's documented icon substitute).

## Run

Any static file server, e.g.:

```bash
python3 -m http.server 4310 --directory maintec-site
# open http://localhost:4310
```

## Pages & flow

- **Home** — hero (`HALLO COLLEGA`), brand manifesto + 3 pillars, vacancy grid with
  working filters, employer CTA band, dark footer.
- Click any **vacancy card** → **vacancy detail** (hero + responsibilities + benefits)
  with a sticky apply form → submit shows the **"Welkom collega!"** confirmation.
- **Terug naar vacatures** returns home. The header is transparent over the dark hero
  and turns solid white on scroll.

## Files

| File | Contents |
|---|---|
| `index.html` | Document shell — loads `styles.css`, Lucide, `app.js` |
| `styles.css` | Design tokens (color/type/radii/shadow) + all component styles |
| `app.js` | Data, primitives (button/tag/eyebrow/bracket), sections, routing, apply flow |
| `assets/fonts/` | Rift Bold, Transducer Regular, Museo Sans 900 (self-hosted) |
| `assets/img/` | Official Maintec photography used by the pages |
| `assets/logo/` | Maintec logos (black / white / orange) |

## Notes

- Copy is **Dutch** with English taglines; people are **collega's**, never "kandidaten".
- One orange accent per view; tight 4px button / 8px card radii; restrained shadows.
- Responsive: 3-col vacancy grid → 2-col → 1-col; nav collapses to a menu button on mobile.
- Source bundle (brand guide, full design system) lives in
  `../design_extract/maintec-design-system-template/`.
