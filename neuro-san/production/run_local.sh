#!/usr/bin/env bash
# =============================================================================
# Start de VIF-service lokaal — één commando, geen echte API-sleutels nodig.
#   ./run_local.sh          → DEV_MODE: mails naar data/outbox/, merkfoto als beeld
# Wil je met échte sleutels draaien? Vul .env met echte waarden en haal
# DEV_MODE eruit (zie INRICHTEN.md).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

# 0. Geschikte Python zoeken (3.10 of nieuwer — de code gebruikt moderne type-hints)
PY=""
for kandidaat in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$kandidaat" > /dev/null 2>&1; then
    versie=$("$kandidaat" -c 'import sys; print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null || echo 0)
    if [ "$versie" -ge 310 ]; then PY="$kandidaat"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "❌ Python 3.10 of nieuwer is nodig (jouw Mac heeft alleen een oudere versie)."
  echo "   Oplossing: download en installeer Python via https://www.python.org/downloads/"
  echo "   (kies de macOS-installer), sluit Terminal, open 'm opnieuw en draai dit script nog eens."
  exit 1
fi
echo "› Python gevonden: $($PY --version)"

# 1. Virtuele omgeving + dependencies (herbouw de omgeving als die met een te oude Python is gemaakt)
if [ -d .venv ]; then
  venv_versie=$(.venv/bin/python -c 'import sys; print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null || echo 0)
  if [ "$venv_versie" -lt 310 ]; then
    echo "› Bestaande .venv gebruikt een te oude Python — opnieuw aanmaken..."
    rm -rf .venv
  fi
fi
if [ ! -d .venv ]; then
  echo "› Python-omgeving aanmaken (.venv)..."
  "$PY" -m venv .venv
fi
echo "› Dependencies installeren/controleren... (eerste keer duurt dit enkele minuten)"
LOG=".venv/pip-install.log"
ok=1
.venv/bin/pip install --upgrade pip > "$LOG" 2>&1 || ok=0
if [ "$ok" = "1" ]; then
  .venv/bin/pip install -r requirements.txt >> "$LOG" 2>&1 || ok=0
fi
if [ "$ok" != "1" ]; then
  echo "❌ Installatie van de dependencies faalde. Laatste regels van het log ($LOG):"
  echo "─────────────────────────────────────────────────────────────"
  tail -30 "$LOG"
  echo "─────────────────────────────────────────────────────────────"
  echo "Tip: stuur bovenstaande regels door, dan kijken we mee. Controleer ook je internetverbinding."
  exit 1
fi
echo "› Dependencies geïnstalleerd ✓"

# 2. .env — maak een werkende DEV-configuratie als er nog geen is
if [ ! -f .env ]; then
  echo "› Geen .env gevonden — DEV-configuratie aanmaken (geen echte sleutels nodig)..."
  SIGNING=$(openssl rand -hex 32 2>/dev/null || echo "dev-signing-secret-0000000000000000")
  TIGRIS=$(openssl rand -hex 16 2>/dev/null || echo "dev-tigris-secret")
  cat > .env << EOF
# DEV-configuratie — automatisch aangemaakt door run_local.sh
# Voor productie: zie .env.example en INRICHTEN.md
DEV_MODE=1
META_ACCESS_TOKEN=dev-dummy
META_AD_ACCOUNT_ID=0
META_PAGE_ID=0
OPENAI_API_KEY=sk-dev-dummy
RESEND_API_KEY=re_dev_dummy
APPROVAL_TO=dev@example.com
PUBLIC_BASE_URL=http://localhost:8000
SIGNING_SECRET=${SIGNING}
TIGRIS_SHARED_SECRET=${TIGRIS}
EOF
else
  echo "› Bestaande .env gevonden — die configuratie wordt gebruikt."
fi

# Zorg dat .env eindigt met een nieuwe regel (anders plakt de eerste aanvulling
# vast aan de laatste bestaande regel en wordt die onleesbaar)
if [ -s .env ] && [ "$(tail -c 1 .env)" != "" ]; then
  echo >> .env
fi

# Vul ontbrekende verplichte sleutels aan (een oude/onvolledige .env mag de start niet blokkeren)
for sleutel in TIGRIS_SHARED_SECRET SIGNING_SECRET PUBLIC_BASE_URL META_ACCESS_TOKEN \
               META_AD_ACCOUNT_ID META_PAGE_ID OPENAI_API_KEY RESEND_API_KEY APPROVAL_TO; do
  if ! grep -q "^${sleutel}=" .env; then
    case "$sleutel" in
      TIGRIS_SHARED_SECRET|SIGNING_SECRET) waarde=$(openssl rand -hex 16 2>/dev/null || echo "dev-secret") ;;
      PUBLIC_BASE_URL) waarde="http://localhost:8000" ;;
      APPROVAL_TO)     waarde="dev@example.com" ;;
      META_AD_ACCOUNT_ID|META_PAGE_ID) waarde="0" ;;
      *)               waarde="dev-dummy" ;;
    esac
    echo "› Ontbrekende sleutel aangevuld in .env: ${sleutel}"
    printf '%s=%s\n' "$sleutel" "$waarde" >> .env
  fi
done

SECRET=$(grep '^TIGRIS_SHARED_SECRET=' .env | head -1 | cut -d= -f2- || true)
DEVREGEL=""
if grep -q '^DEV_MODE=1' .env 2>/dev/null; then
  DEVREGEL="  Goedkeur-mails (DEV):   data/outbox/  (open de .html in je browser)"
fi
echo
echo "════════════════════════════════════════════════════════════"
echo "  VIF-service start op:   http://localhost:8000"
echo "  Upload-pagina:          http://localhost:8000/vif"
echo "  Geheim voor de pagina:  ${SECRET:-(zie TIGRIS_SHARED_SECRET in .env)}"
[ -n "$DEVREGEL" ] && echo "$DEVREGEL"
echo "  Gegenereerde beelden:   data/beelden/"
echo "  Stoppen:                Ctrl+C"
echo "════════════════════════════════════════════════════════════"
echo
if curl -s -m 2 http://localhost:8000/health > /dev/null 2>&1; then
  echo "⚠️  Er draait al een service op poort 8000 — waarschijnlijk een eerder gestart venster."
  echo "   Open gewoon http://localhost:8000/vif, of stop de andere eerst met Ctrl+C."
  exit 0
fi
exec .venv/bin/uvicorn webhook:app --reload --port 8000
