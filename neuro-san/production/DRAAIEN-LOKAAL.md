# VIF-service lokaal draaien (op je eigen Mac)

Alles draait op je laptop — **zonder** dat je Meta-, OpenAI- of Resend-sleutels
nodig hebt. In DEV-modus wordt de beeldgeneratie vervangen door de merkfoto
(mét logo-overlay), gaan goedkeur-mails naar `data/outbox/` als HTML-bestand,
draait Salesforce in dry-run en wordt een Meta-fout netjes in de mail gemeld.

## Snelstart (één keer instellen, daarna één commando)

Open Terminal en plak:

```bash
cd ~/Documents/GitHub/neurosan/neuro-san/production
chmod +x run_local.sh
./run_local.sh
```

Het script maakt zelf een Python-omgeving, installeert de dependencies,
genereert een werkende DEV-configuratie (`.env`) en start de server.
Daarna:

1. Open **http://localhost:8000/vif** in je browser.
2. Plak het **geheim** dat het script in je terminal toont.
3. Upload een VIF (Word of PDF) — geen VIF bij de hand? Draai eerst
   `.venv/bin/python selftest_vif.py`; die maakt `data/voorbeeld_vif.docx`.
4. Volg de keten live in je terminal. Het resultaat:
   - **Goedkeur-mail** → `data/outbox/…-Akkoord-nodig-….html` (openen in browser)
   - **Vacaturebeeld** → `data/beelden/VIF-….png`
   - **Agent-dialoog** → http://localhost:8000/neuro-debug?token=JOUW_GEHEIM

## Zelftests (los van de server)

```bash
.venv/bin/python selftest_vif.py    # VIF-parser + tekstketen (geen keys nodig)
.venv/bin/python selftest_sf.py     # Salesforce-koppeling (dry-run zonder creds)
.venv/bin/python selftest_neuro.py  # Neuro San-brein (vereist draaiende server, zie onder)
```

## Het Neuro San-'brein' lokaal draaien (optioneel)

Zonder brein valt de keten automatisch terug op de ingebouwde agents — dat
werkt prima. Wil je het volledige AAOSA-netwerk (rijkere teksten + sourcing-
advies), dan staat de netwerkdefinitie nu in deze repo:
`registries/generated/neuro_san_vif_to_publish_sourcing.hocon`.

```bash
cd ~/Documents/GitHub/neurosan/neuro-san/production
.venv/bin/pip install neuro-san
export ANTHROPIC_API_KEY=sk-ant-...        # het brein heeft wél een Claude-sleutel nodig
export AGENT_MANIFEST_FILE=registries/manifest.hocon
.venv/bin/python -m neuro_san.service.agent_main_loop --http_port 8080
```

Draait de neuro-san server op poort 8080, dan pikt de VIF-service 'm
automatisch op (instelling `NEURO_SAN_URL`, standaard `http://localhost:8080`).
Wijkt het startcommando af in jouw neuro-san-versie, kijk dan in de
documentatie: https://github.com/cognizant-ai-lab/neuro-san

## Overstappen naar échte sleutels

1. Volg `INRICHTEN.md` (stap 1 t/m 4) om alle sleutels te verzamelen.
2. Vul ze in `.env` in en **verwijder de regel `DEV_MODE=1`**.
3. Herstart `./run_local.sh`.

| Zonder deze sleutel | Gebeurt er |
|---|---|
| `OPENAI_API_KEY` | merkfoto + overlay als vacaturebeeld (keten loopt door) |
| `RESEND_API_KEY` | mail als HTML in `data/outbox/` (alleen in DEV_MODE) |
| `SF_CLIENT_ID/SECRET` | Salesforce dry-run: payload wordt gelogd, niet weggeschreven |
| `META_ACCESS_TOKEN` | campagne-aanmaak faalt gecontroleerd; melding in de goedkeur-mail |
| `ANTHROPIC_API_KEY` | teksten via het regel-gebaseerde fallback-sjabloon i.p.v. Claude |
