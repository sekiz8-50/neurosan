# VIF Automation — AI Solution Summary

**TecqGroep · Maintec & Tecforce**

## In one sentence

Sales uploads a single vacancy intake form (VIF); an AI system then writes the vacancy,
generates an on-brand image and a short video, records everything in Salesforce/Tigris,
and stages a Meta lead campaign — all automatically. Marketing approves with one click and
the vacancy goes live. The recruiter spends their time on candidates instead of data entry.

## How it works — the pipeline

1. **Upload** — Sales posts the Word/PDF intake form at `maintec.nl/vif` (or straight from Tigris).
2. **Completeness check** — A gatekeeper agent blocks and returns the form to sales if any core
   field is missing (job title, location, salary/CBA, experience, tasks), so nothing incomplete
   is ever published.
3. **The brain writes** — A team of collaborating AI agents produces the vacancy text, SEO,
   FAQ, ad variants, and the creative briefs.
4. **Media** — An on-brand image is generated; from that image a short recruitment video
   (≤ 8 seconds) is produced in the background.
5. **Tigris/Salesforce** — A complete vacancy record is created, with the image and video stored
   persistently (login-free links).
6. **Meta campaign** — A lead campaign is staged (PAUSED): ad set with radius targeting, an
   Instant Form, five photo ads and five video ads. Leads are traceable to the vacancy via an
   "App Id" tracking parameter.
7. **Approval** — Marketing receives an approval email and publishes with one click. Nothing goes
   live without this human check.

## The brain — a team of AI specialists

Each agent is a focused specialist; an orchestrator runs them in sequence and bundles the result
into one executable brief:

- **Intake parser & requirement validator** — reads the VIF, checks completeness (strict).
- **Copywriter** — writes appealing, on-brand vacancy text (with a mandatory revision loop).
- **SEO specialist** — meta titles, description, slug, keywords.
- **GEO/LLM specialist** — FAQ for findability in AI assistants.
- **Performance marketeer** — five Meta ad variants (employment-compliant targeting).
- **Designer** — creative brief + image prompt (safety gear, diversity, clean, on-brand).
- **Video director** — turns the still image into a short video (subtle, safe motion, ≤ 8s).
- **Corporate recruiter** — sourcing advice (boolean strings, channels, outreach angle).
- **ATS publisher** — maps the vacancy to the Salesforce/Tigris schema.
- **Brand & legal guardian** — final check on tone, truthfulness and compliance (go/no-go).

## Built-in safeguards (quality is guaranteed, not hoped for)

Each rule is enforced twice: as an instruction to the agents **and** as a code backstop.

- **Client anonymity** — the end client's name never appears in public text.
- **Salary always in the vacancy text**; in ads only the attractive upper bound ("up to € X").
- **No internal clauses** (e.g. the temp-to-perm "1040 hours" clause) in any public text.
- **Geo fail-closed** — a campaign never targets the whole country; if the location can't be
  resolved to a radius, the campaign is blocked rather than wasting budget.
- **Lead ↔ vacancy coupling verified** before anything can go live (fail-closed on the App Id).
- **Resilient & gated** — a failure in image, video, Meta or mail never breaks the rest; media
  generation is off by default and switched on per environment.

## Media generation

- **Image** — a realistic, on-brand image with the Maintec house style; a clean version (no text)
  and a branded version (with text overlay).
- **Video** — created asynchronously so it never delays the approval email. The paid video job is
  persisted immediately and the finished video is stored durably in Salesforce, so a paid job is
  never lost — even across a restart. Video ads are added to the campaign only once the video is
  actually ready, and auto-activated if the campaign is already live.

## Email provider & delivery

All notification and approval emails are sent from a real `@tecqgroep.com` mailbox via the
Microsoft 365 Graph API (responsive, dark-mode-safe templates).

## The business case (ROI)

- **~ € 71,000 saved per year** · **~ € 5,900/month** · **~ 110 hours freed per month** ·
  **~ 0.8 FTE freed up**.
- Per vacancy: **~ 170 minutes of manual work becomes ~ 5 minutes** (review & approve) —
  **≈ € 149 net saved** after AI and review costs.
- Assumption: ~ 40 vacancies/month across Maintec + Tecforce at € 55/hour all-in.

**The real upside goes beyond hours:** faster time-to-fill (a vacancy live the same day),
better organic findability, full lead tracking, and scale without adding headcount. A single
extra placement per month from faster turnaround already outweighs the entire labour saving.

## Status

Not a prototype — the full chain runs end-to-end in production (Render): the AI brain, image and
video generation, Salesforce/Tigris records, the Meta lead campaign, and one-click approval.
Ongoing cost is negligible (~ € 2–3 per vacancy in AI + ~ € 25/month hosting).

**Next steps:** recruiter sourcing, an own photo library, direct website publishing, and roll-out
across both Maintec and Tecforce.

*Join the Future Techforce.*
