# Neuro San — vacature → beeld → Meta-campagne (mock demo)

End-to-end **mock** van de automatisering: zodra in Salesforce/Tigris een vacature
wordt gepubliceerd, zet Neuro San automatisch een passend beeld én een
gesegmenteerde Meta-campagne klaar. Marketing krijgt één goedkeur-mail; pas na
akkoord gaat de campagne live.

```
Tigris → Analyse → Firefly-beeld → Meta-campagne (PAUSED) → goedkeur-mail → (na akkoord) LIVE
```

## Demo bekijken
Open **`demo.html`** in de browser (of via het preview-paneel). Eén pagina die de
hele flow visueel doorloopt, met het echte beeld en de gegenereerde mail.

## Zelf draaien
```bash
python3 pipeline_mock.py            # draait de flow, stopt bij 'wacht op goedkeuring'
python3 pipeline_mock.py --approve  # simuleert ook de goedkeuring + publicatie
```
Genereert in `output/`: `campagne.json` en `goedkeur-mail.html`.

## Bestanden
| Bestand | Wat |
|---|---|
| `sample_vacancy.json` | Voorbeeld-payload zoals Tigris bij publicatie verstuurt |
| `agent_network.hocon` | NeuroSan agent-netwerk (productie-definitie) |
| `pipeline_mock.py` | Orkestrator die de flow stap voor stap draait (mock) |
| `coded_tools/analyse_agent.py` | Doelgroep, merk-context (Maintec/Tecforce), toon, kanalen |
| `coded_tools/firefly_beeld_agent.py` | Bouwt beeld-prompt + roept Adobe Firefly aan |
| `coded_tools/meta_campagne_agent.py` | Gesegmenteerde, getargete Meta-campagne (status PAUSED) |
| `coded_tools/approval_agent.py` | Goedkeur-mail met Goedkeuren/Afkeuren-links |
| `demo.html` | Visuele stakeholder-demo |

## Wat is mock, wat wordt productie
- **Trigger** — mock: `sample_vacancy.json`. Productie: Salesforce Platform Event / outbound webhook → NeuroSan-endpoint.
- **Beeld** — mock: echt Adobe Stock-voorbeeld (Firefly-generatie is in deze omgeving niet beschikbaar). Productie: Adobe Firefly Services Text-to-Image uit de auto-prompt.
- **Campagne** — mock: JSON-structuur. Productie: Meta Marketing API (campagne + ad sets aangemaakt op **PAUSED**).
- **Goedkeuring** — mock: HTML-mail met dummy-links. Productie: SMTP/SendGrid/MS Graph + HMAC-ondertekende, eenmalige token-URL's.
- **Publicatie** — mock: status → ACTIVE. Productie: Meta API zet campagne op ACTIVE, uitsluitend getriggerd door de goedgekeurde link.

## Nodig voor de productie-bouw
- Salesforce/Tigris: rechten om een Platform Event of outbound webhook te configureren.
- Adobe Firefly Services: API-key + entitlement voor Text-to-Image.
- Meta: Business-account, Marketing API-toegang, ad-account-id, app + token.
- Endpoint/host voor het NeuroSan-netwerk en de goedkeur-links (bv. `automation.tecqgroep.com`).
