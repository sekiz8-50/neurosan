"""Koppeling naar het draaiende Neuro San-netwerk (het 'brein').

Roept het AAOSA-netwerk `generated/neuro_san_vif_to_publish_sourcing` aan via de
neuro-san HTTP streaming_chat-API, leest de stream en geeft de finale tekst +
de geëxtraheerde handoff_json terug. Dit netwerk valideert/professionaliseert de
VIF en levert een handoff — het voert zélf geen externe acties uit. Die acties
(beeld, Tigris, Meta, mail) doet onze production-pijplijn met de bestaande tools.

Server draait lokaal (NEURO_SAN_URL, default http://localhost:8080).
"""
import json
import re

import requests

from config import cfg

# Het top-level netwerk-antwoord komt als AGENT_FRAMEWORK; AI is de fallback.
# (MINIMAL-filter laat dit eindbericht soms vallen — gebruik daarom MAXIMAL.)
FRAMEWORK_TYPE = "AGENT_FRAMEWORK"
AI_TYPE = "AI"


def beschikbaar(timeout: int = 4) -> bool:
    """Snelle check of de neuro-san server bereikbaar is (LLM-vrij)."""
    try:
        r = requests.get(f"{cfg.NEURO_SAN_URL}/api/v1/list", timeout=timeout)
        return r.ok
    except Exception:
        return False


def run_network(user_text: str, sly_data: dict | None = None,
                agent: str | None = None, timeout: int = 1800) -> dict:
    """Stuurt user_text naar het netwerk en verzamelt het stream-antwoord.

    Gebruikt de MAXIMAL-filter zodat het finale AGENT_FRAMEWORK-bericht (de
    gebundelde handoff van de orchestrator) gegarandeerd binnenkomt.
    Retour: {"text": finale_tekst, "framework": [...], "ai": [...], "sly_data": {...}}.
    """
    agent = agent or cfg.NEURO_SAN_AGENT
    url = f"{cfg.NEURO_SAN_URL}/api/v1/{agent}/streaming_chat"
    req = {"user_message": {"type": "HUMAN", "text": user_text},
           "chat_filter": {"chat_filter_type": "MAXIMAL"}}
    if sly_data:
        req["sly_data"] = sly_data

    with requests.post(url, json=req, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        return _verzamel(r.iter_lines(decode_unicode=True))


def _afzender(resp: dict) -> str:
    """Welke agent stuurde dit bericht? Laatste schakel in de 'origin'-keten."""
    origin = resp.get("origin") or []
    if isinstance(origin, list) and origin:
        last = origin[-1]
        if isinstance(last, dict):
            return last.get("tool") or last.get("agent") or ""
        return str(last)
    return ""


def _verzamel(lines) -> dict:
    """Leest de newline-JSON-stream: bewaart het finale antwoord (AGENT_FRAMEWORK > AI)
    én de volledige transcript (alle berichten met afzender) voor inzicht/debug."""
    framework: list[str] = []
    ai: list[str] = []
    transcript: list[dict] = []
    returned_sly: dict = {}
    for line in lines:
        if not line or not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = msg.get("response", {}) or {}
        t, txt = resp.get("type"), resp.get("text")
        if txt:
            transcript.append({"from": _afzender(resp), "type": t, "text": txt})
        if txt and t == FRAMEWORK_TYPE:
            framework.append(txt)
        elif txt and t == AI_TYPE:
            ai.append(txt)
        for bron in (msg.get("sly_data"), resp.get("sly_data")):
            if isinstance(bron, dict):
                returned_sly.update(bron)
    finale = (framework or ai or [""])[-1]
    return {"text": finale, "framework": framework, "ai": ai,
            "transcript": transcript, "sly_data": returned_sly}


def extract_handoff(text: str) -> dict | None:
    """Haalt het handoff-JSON-object uit de (markdown-)tekst van de orchestrator."""
    if not text:
        return None
    # 1) ```json ... ``` codeblok
    blokken = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    kandidaten = list(blokken)
    # 2) anders: het grootste {...}-blok in de tekst
    if not kandidaten:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            kandidaten.append(text[s:e + 1])
    for blok in sorted(kandidaten, key=len, reverse=True):
        try:
            return json.loads(blok)
        except json.JSONDecodeError:
            continue
    return None


def handoff_payload(text: str) -> dict | None:
    """Geeft de bruikbare handoff-inhoud terug: het 'Response'-deel (AAOSA-wrapper) of het hele object."""
    h = extract_handoff(text)
    if not h:
        return None
    resp = h.get("Response")
    return resp if isinstance(resp, dict) else h
