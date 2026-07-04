/* Maintec Website UI Kit — Vacancy detail + apply flow */

function VacancyDetail({ v, onBack }) {
  const [applied, setApplied] = useState(false);
  const benefits = [
    "Vast dienstverband bij Maintec — jij bent collega, geen kandidaat",
    "Persoonlijke begeleiding door een vaste consultant",
    "Toegang tot onze eigen vakschool: reskilling & upskilling",
    "Werken met topmateriaal bij de gaafste technische bedrijven",
  ];
  return (
    <div>
      {/* hero */}
      <section style={{ position: "relative", background: "#000", color: "#fff", overflow: "hidden", marginTop: -76 }}>
        <div style={{ position: "absolute", inset: 0, left: "46%", backgroundImage: `url(${v.img})`,
          backgroundSize: "cover", backgroundPosition: "center" }} />
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg,#000 40%,rgba(0,0,0,.4) 75%,transparent)" }} />
        <div style={{ position: "relative", maxWidth: 1240, margin: "0 auto", padding: "110px 32px 64px" }}>
          <button onClick={onBack} style={{ background: "transparent", border: "none", color: "var(--ink-300)",
            fontFamily: "var(--font-body)", fontSize: 14, cursor: "pointer", display: "inline-flex",
            alignItems: "center", gap: 7, marginBottom: 34 }}>
            <Icon name="arrow-left" size={16} /> Terug naar vacatures
          </button>
          <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
            <Tag variant="orange">{v.type}</Tag><Tag variant="dark">{v.field}</Tag>
          </div>
          <h1 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase", color: "#fff",
            fontSize: 60, lineHeight: 0.92, letterSpacing: "-.01em", maxWidth: 620, margin: 0 }}>{v.title}</h1>
          <div style={{ display: "flex", gap: 26, marginTop: 26, color: "var(--ink-200)", fontSize: 15,
            fontFamily: "var(--font-body)", flexWrap: "wrap" }}>
            {[["map-pin", v.region], ["clock", v.hours], ["wallet", v.salary], ["briefcase", v.type]].map(([ic, t]) => (
              <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                <span style={{ color: "var(--orange-500)" }}><Icon name={ic} size={17} /></span>{t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* body */}
      <section style={{ background: "#fff", padding: "72px 32px" }}>
        <div style={{ maxWidth: 1240, margin: "0 auto", display: "grid",
          gridTemplateColumns: "1.7fr 1fr", gap: 56 }}>
          <div>
            <h3 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase", fontSize: 26,
              letterSpacing: "-.01em", color: "#000", margin: "0 0 14px" }}>Over de functie</h3>
            <p style={{ fontFamily: "var(--font-body)", fontSize: 17, lineHeight: 1.65, color: "var(--ink-600)" }}>
              Als {v.title.toLowerCase()} werk je samen met een hecht team aan uitdagende projecten
              in de {v.field.toLowerCase()}. Je krijgt de beste begeleiding die je maar kunt wensen
              en de ruimte om jezelf te blijven ontwikkelen. Bij Maintec sta je er nooit alleen voor —
              we bundelen onze krachten.
            </p>
            <h3 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase", fontSize: 26,
              letterSpacing: "-.01em", color: "#000", margin: "40px 0 16px" }}>Wat wij bieden</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {benefits.map(b => (
                <div key={b} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <span style={{ color: "var(--orange-500)", marginTop: 1 }}><Icon name="check" size={20} stroke={2.6} /></span>
                  <span style={{ fontFamily: "var(--font-body)", fontSize: 16, lineHeight: 1.5, color: "var(--ink-700)" }}>{b}</span>
                </div>
              ))}
            </div>
          </div>

          {/* apply card */}
          <div>
            <div style={{ position: "sticky", top: 96, border: "1px solid var(--ink-200)",
              borderRadius: 8, padding: 26, background: "#fff", boxShadow: "var(--shadow-md)" }}>
              {!applied ? (
                <>
                  <Eyebrow>Solliciteer direct</Eyebrow>
                  <div style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
                    fontSize: 24, margin: "10px 0 18px", letterSpacing: "-.01em" }}>Word collega</div>
                  {["Naam", "E-mailadres", "Telefoon"].map(l => (
                    <div key={l} style={{ marginBottom: 12 }}>
                      <label style={{ display: "block", fontFamily: "var(--font-body)", fontSize: 11,
                        textTransform: "uppercase", letterSpacing: ".06em", color: "var(--ink-500)", marginBottom: 6 }}>{l}</label>
                      <input style={{ width: "100%", fontFamily: "var(--font-body)", fontSize: 15,
                        padding: "11px 13px", border: "1.5px solid var(--ink-200)", borderRadius: 4, outline: "none" }}
                        onFocus={e => e.target.style.borderColor = "var(--orange-500)"}
                        onBlur={e => e.target.style.borderColor = "var(--ink-200)"} />
                    </div>
                  ))}
                  <div style={{ marginTop: 8 }}>
                    <Button variant="primary" icon="arrow-right" style={{ width: "100%", justifyContent: "center" }}
                      onClick={() => setApplied(true)}>Verstuur sollicitatie</Button>
                  </div>
                  <p style={{ fontFamily: "var(--font-body)", fontSize: 12, color: "var(--ink-400)",
                    marginTop: 14, lineHeight: 1.5 }}>Of bel ons direct — we denken graag met je mee.</p>
                </>
              ) : (
                <div style={{ textAlign: "center", padding: "20px 4px" }}>
                  <div style={{ width: 56, height: 56, borderRadius: 999, background: "var(--orange-500)",
                    display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 18px", color: "#fff" }}>
                    <Icon name="check" size={30} stroke={3} />
                  </div>
                  <div style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
                    fontSize: 24, letterSpacing: "-.01em" }}>Welkom collega!</div>
                  <p style={{ fontFamily: "var(--font-body)", fontSize: 15, lineHeight: 1.55,
                    color: "var(--ink-500)", marginTop: 10 }}>
                    We hebben je sollicitatie ontvangen en nemen snel contact met je op.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

Object.assign(window, { VacancyDetail });
