"""AI-kostenteller per VIF-run.

Telt het tokenverbruik van élke Claude-aanroep (het 11-agent-brein + de
fallback-agents) en het aantal gegenereerde beelden, en vertaalt dat naar
US-dollars en euro's — zodat de marketingmail exact laat zien wat de aanvraag
aan AI-credits heeft gekost.

De teller leeft in een contextvar: pipeline.run_vif() start 'm aan het begin
van een run; de agent-modules melden hun verbruik via add_llm()/add_beeld()
zonder dat er een object door de hele keten hoeft te worden doorgegeven.
Elke achtergrond-run krijgt zijn eigen kopie van de context, dus gelijktijdige
VIF's tellen niet door elkaar heen.
"""
import contextvars

from config import cfg

_huidige: contextvars.ContextVar = contextvars.ContextVar("kosten", default=None)


class Kosten:
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self.beelden = 0

    def add_llm(self, usage) -> None:
        try:
            self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
            self.calls += 1
        except Exception:
            pass

    def add_beeld(self, n: int = 1) -> None:
        self.beelden += n

    def _usd(self) -> float:
        return (self.input_tokens / 1_000_000 * cfg.PRIJS_INPUT_PER_MILJOEN_USD
                + self.output_tokens / 1_000_000 * cfg.PRIJS_OUTPUT_PER_MILJOEN_USD
                + self.beelden * cfg.PRIJS_BEELD_PER_STUK_USD)

    def samenvatting(self) -> dict:
        usd = self._usd()
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "totaal_tokens": self.input_tokens + self.output_tokens,
            "calls": self.calls,
            "beelden": self.beelden,
            "usd": round(usd, 4),
            "eur": round(usd * cfg.USD_EUR_KOERS, 2),
            "model": cfg.ANTHROPIC_MODEL,
        }


def start() -> Kosten:
    """Begin een nieuwe telling voor deze run (reset)."""
    k = Kosten()
    _huidige.set(k)
    return k


def add_llm(usage) -> None:
    """Meld het tokenverbruik van één Claude-aanroep (msg.usage). Faalt stil."""
    k = _huidige.get()
    if k is not None:
        k.add_llm(usage)


def add_beeld(n: int = 1) -> None:
    """Meld dat er n beeld(en) zijn gegenereerd (OpenAI gpt-image-1)."""
    k = _huidige.get()
    if k is not None:
        k.add_beeld(n)


def samenvatting() -> dict | None:
    """De actuele kostensamenvatting van deze run, of None als er niet geteld wordt."""
    k = _huidige.get()
    return k.samenvatting() if k is not None else None
