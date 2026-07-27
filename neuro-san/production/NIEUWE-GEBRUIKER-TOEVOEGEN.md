# Nieuwe gebruiker toevoegen die de VIF mag activeren

Korte checklist om een nieuwe (niet-admin) collega de VIF-stroom "NeuroSan" te
laten indienen in Salesforce/Tigris. Doorloop de stappen van boven naar beneden.

> **Waarom dit nodig is:** een admin (bv. jij) werkt automatisch omdat een admin
> toegang heeft tot álle objecten. Een gewone gebruiker met een **Salesforce
> Platform**-licentie mist een paar specifieke rechten. Zonder die rechten geeft
> de stroom de melding *"In deze stroom heeft zich een onafgehandelde fout
> voorgedaan"*.

---

## Stap 1 — Machtigingenset toewijzen

**Set-up → Machtigingensets → "Neuro San toegang" → Toewijzingen beheren →
Toewijzingen toevoegen → selecteer de gebruiker → Toewijzen.**

Deze set regelt in één keer:
- toegang tot de VIF-schermflow;
- **Hoofdtoegang tot externe referentie** = `Neuro_San - NeuroSan` (staat er al in);
- leesrecht op **Gebruikers-externe referenties** (zie stap 2 — controleer dit).

## Stap 2 — Leesrecht op "Gebruikers-externe referenties" controleren

Dit is het recht dat de callout naar Render laat werken.

**Machtigingenset "Neuro San toegang" → Objectinstellingen → zoek
"Gebruikers-externe referenties" (User External Credentials) → Bewerken →
vink _Lezen_ aan → Opslaan.**

> ⚠️ **Let op — verwar dit NIET met "Externe beheerde accounts".** Dat is een
> ánder object en de Salesforce Platform-licentie blokkeert leesrecht daarop
> (foutmelding bij opslaan). Je hebt alleen **"Gebruikers-externe referenties"**
> nodig.

## Stap 3 — Stroom staat op systeemcontext

De stroom "NeuroSan" moet draaien in **Systeemcontext met delen — Dwingt toegang
op recordniveau af**. Dit staat al zo ingesteld en hoef je per nieuwe gebruiker
**niet** aan te passen. (Instelling zit in Flow Builder → ⚙ → "De manier waarop
de stroom wordt uitgevoerd".) "Met delen" houdt de record-sharing actief, dus de
gebruiker ziet alleen zijn eigen opdrachtgevers/vacatures.

## Stap 4 — Testen

Laat de nieuwe gebruiker een VIF indienen onder een opdrachtgever waar hij
toegang toe heeft.

- **Werkt het** → klaar. ✅
- **Fout?** → zet een Debug Log op de gebruiker (**Set-up →
  Foutopsporingslogboeken → Tracering toevoegen → Gebruiker**), laat hem opnieuw
  proberen, en zoek in de log op `FLOW_ELEMENT_ERROR` of `FATAL_ERROR`. Die regel
  noemt exact welk recht of object ontbreekt.

---

## Snelle diagnose van veelvoorkomende fouten

| Foutmelding in de log | Oorzaak | Oplossing |
|---|---|---|
| `You don't have read permissions on the User External Credential object` | Leesrecht op Gebruikers-externe referenties mist | Stap 2 |
| Fout bij `getCV` / `vulBody` (vóór de callout) | Data-stap heeft geen rechten | Stroom op systeemcontext (stap 3) |
| Melding bij opslaan: *"licentie staat de machtiging niet toe: Externe beheerde accounts lezen"* | Verkeerd object aangevinkt | Gebruik **Gebruikers-externe referenties**, niet Externe beheerde accounts |

> **Nog robuuster (optioneel, eenmalig):** de callout kan ook via een klein stukje
> Apex `without sharing` lopen. Dan hoeft géén enkele nieuwe gebruiker meer een
> External-Credential-objectrecht — stap 2 vervalt dan voor iedereen. Vraag hierom
> als je veel niet-admin gebruikers gaat toevoegen.
