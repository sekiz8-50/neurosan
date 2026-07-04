"""Google-Trends-specialist — populariteit van functie + plaats.

Gebruikt pytrends (onofficiële Google Trends-client). Trends is grillig en kan
rate-limiten; daarom faalt deze tool NOOIT hard — bij elke fout valt ze terug op
een neutrale score, zodat de keten doordraait. De uitkomst voedt de
campagnestrategie (budget/urgentie) en de copy (schaarste-framing).
"""


def popularity(functie: str, plaats: str = "", geo: str = "NL") -> dict:
    """Geeft {score 0-100, interesse_functie, interesse_plaats, bron, trending}.

    score = relatieve zoekinteresse in de functie (12 maanden, NL). Faalt stil
    terug op een neutrale score 50 met bron 'fallback'.
    """
    neutraal = {"score": 50, "interesse_functie": None, "interesse_plaats": None,
                "bron": "fallback", "trending": "onbekend"}
    if not functie:
        return neutraal
    try:
        from pytrends.request import TrendReq

        # Alleen de functie in de payload: Google Trends schaalt termen relatief, en een
        # plaatsnaam scoort altijd hoog — die zou de functie-score naar ~0 drukken.
        py = TrendReq(hl="nl-NL", tz=60)
        py.build_payload([functie], timeframe="today 12-m", geo=geo)
        df = py.interest_over_time()
        if df is None or df.empty or functie not in df:
            return neutraal
        gem = float(df[functie].mean())
        # trending: laatste maand (≈4 weken) t.o.v. het jaargemiddelde
        trending = "stabiel"
        if gem:
            laatste = float(df[functie].tail(4).mean())
            if laatste > gem * 1.15:
                trending = "stijgend"
            elif laatste < gem * 0.85:
                trending = "dalend"
        return {"score": max(0, min(100, int(round(gem)))), "interesse_functie": round(gem, 1),
                "interesse_plaats": None, "bron": "google-trends", "trending": trending}
    except Exception as e:
        print(f"[Google-Trends] viel terug op neutrale score: {e}")
        return neutraal
