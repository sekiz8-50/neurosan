/* Maintec Website UI Kit — Home page sections */

const VACANCIES = [
  { id: 1, title: "Monteur Zonnepanelen", region: "Utrecht", hours: "38 uur", type: "Fulltime", field: "Installatietechniek", img: "../../assets/imagery/worker-duct-install.jpg", salary: "€2.800 – €3.600" },
  { id: 2, title: "Onderhoudsmonteur", region: "Amersfoort", hours: "40 uur", type: "Fulltime", field: "Werktuigbouw", img: "../../assets/imagery/workers-pipes-trio.jpg", salary: "€2.900 – €3.800" },
  { id: 3, title: "Eerste Monteur Elektra", region: "Nijmegen", hours: "36 uur", type: "Fulltime", field: "Elektrotechniek", img: "../../assets/imagery/workers-electrical-panel.jpg", salary: "€3.100 – €4.200" },
  { id: 4, title: "Servicetechnicus", region: "Den Bosch", hours: "40 uur", type: "Fulltime", field: "Service & Onderhoud", img: "../../assets/imagery/worker-laptop-hallway.jpg", salary: "€2.700 – €3.900" },
  { id: 5, title: "Werkvoorbereider Techniek", region: "Eindhoven", hours: "32–40 uur", type: "Parttime", field: "Engineering", img: "../../assets/imagery/worker-smiling-laptop.jpg", salary: "€3.400 – €4.500" },
  { id: 6, title: "Leerling Installatietechniek", region: "Landelijk", hours: "40 uur", type: "Opleiding", field: "Reskilling", img: "../../assets/imagery/workers-pipes-trio.jpg", salary: "Opleiding + salaris" },
];

function Hero({ onCta }) {
  return (
    <section style={{ position: "relative", background: "#000", color: "#fff", overflow: "hidden", marginTop: -76 }}>
      {/* full-bleed photo right */}
      <div style={{ position: "absolute", inset: 0, left: "40%",
        backgroundImage: "url(../../assets/imagery/welder-sparks.jpg)",
        backgroundSize: "cover", backgroundPosition: "right center" }} />
      <div style={{ position: "absolute", inset: 0, left: "26%",
        background: "linear-gradient(90deg,#000 38%,rgba(0,0,0,.55) 62%,rgba(0,0,0,.15) 100%)" }} />
      <div style={{ position: "relative", maxWidth: 1240, margin: "0 auto", padding: "190px 32px 130px" }}>
        <div style={{ maxWidth: 560 }}>
          <Eyebrow>Werken bij Maintec</Eyebrow>
          <h1 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase", color: "#fff",
            fontSize: 92, lineHeight: 0.9, letterSpacing: "-.01em", margin: "18px 0 0" }}>
            Hallo <span style={{ color: "var(--orange-500)" }}>collega</span>
          </h1>
          <p style={{ fontFamily: "var(--font-body)", fontSize: 19, lineHeight: 1.55,
            color: "var(--ink-200)", marginTop: 22, maxWidth: 460 }}>
            Jij kan meer uit je werk halen dan je denkt. Sluit je aan bij een werkgever die
            verder kijkt dan vandaag. Laten we samen onze krachten bundelen.
          </p>
          <div style={{ display: "flex", gap: 14, marginTop: 32 }}>
            <Button variant="primary" size="lg" icon="arrow-right" onClick={onCta}>Bekijk vacatures</Button>
            <Button variant="outline" size="lg" style={{ color: "#fff" }}>Ons verhaal</Button>
          </div>
        </div>
      </div>
      {/* tagline strip */}
      <div style={{ position: "relative", borderTop: "1px solid rgba(255,255,255,.14)",
        padding: "20px 32px" }}>
        <div style={{ maxWidth: 1240, margin: "0 auto", display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
            fontSize: 22, letterSpacing: ".02em" }}>
            Join the future <span style={{ color: "var(--orange-500)" }}>techforce</span>
          </span>
        </div>
      </div>
    </section>
  );
}

function Manifesto() {
  return (
    <section style={{ background: "#fff", padding: "96px 32px" }}>
      <div style={{ maxWidth: 940, margin: "0 auto" }}>
        <Eyebrow>Merkverhaal</Eyebrow>
        <h2 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
          fontSize: 50, lineHeight: 0.98, letterSpacing: "-.01em", color: "#000", margin: "16px 0 0" }}>
          Wij zijn een collectief van<br /><span style={{ color: "var(--orange-500)" }}>gemotiveerde vakspecialisten</span>
        </h2>
        <p style={{ fontFamily: "var(--font-body)", fontSize: 19, lineHeight: 1.6,
          color: "var(--ink-600)", marginTop: 26, maxWidth: 720 }}>
          Zie ons niet als het zoveelste uitzendbureau of detacheerder. Wij zijn op de eerste
          plaats werkgever. Onze mensen zijn geen 'kandidaten' — ze zijn collega's. Wij
          begrijpen de wereld van techniek als geen ander, want we zitten er middenin.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 1,
          marginTop: 48, background: "var(--ink-200)", border: "1px solid var(--ink-200)" }}>
          {[
            ["users", "Hecht team", "Een collectief van collega's, geen losse flexkrachten."],
            ["graduation-cap", "Eigen vakschool", "Opleiding, reskilling én upskilling van technisch talent."],
            ["shield-check", "Echt werkgeverschap", "Vaste begeleiding, goede arbeidsvoorwaarden, aandacht."],
          ].map(([ic, t, d]) => (
            <div key={t} style={{ background: "#fff", padding: "28px 26px" }}>
              <span style={{ color: "var(--orange-500)" }}><Icon name={ic} size={26} stroke={2} /></span>
              <div style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
                fontSize: 20, marginTop: 14, letterSpacing: ".01em" }}>{t}</div>
              <p style={{ fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.55,
                color: "var(--ink-500)", marginTop: 8 }}>{d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function VacancyCard({ v, onOpen }) {
  const [h, setH] = useState(false);
  return (
    <div onClick={() => onOpen(v)} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ background: "#fff", border: "1px solid var(--ink-200)", borderRadius: 8,
        overflow: "hidden", cursor: "pointer", transition: "transform .18s, box-shadow .18s",
        transform: h ? "translateY(-4px)" : "none", boxShadow: h ? "var(--shadow-md)" : "none" }}>
      <div style={{ height: 150, position: "relative", backgroundImage: `url(${v.img})`,
        backgroundSize: "cover", backgroundPosition: "center" }}>
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg,transparent 40%,rgba(0,0,0,.5))" }} />
        <div style={{ position: "absolute", top: 12, left: 12 }}><Tag variant="orange">{v.type}</Tag></div>
      </div>
      <div style={{ padding: "18px 20px 20px" }}>
        <div style={{ fontFamily: "var(--font-body)", fontSize: 11, textTransform: "uppercase",
          letterSpacing: ".06em", color: "var(--ink-400)" }}>{v.field}</div>
        <div style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
          fontSize: 23, lineHeight: 1, letterSpacing: "-.01em", marginTop: 8 }}>{v.title}</div>
        <div style={{ display: "flex", gap: 14, marginTop: 14, color: "var(--ink-500)", fontSize: 13,
          fontFamily: "var(--font-body)" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><Icon name="map-pin" size={15} />{v.region}</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><Icon name="clock" size={15} />{v.hours}</span>
        </div>
      </div>
    </div>
  );
}

function Vacancies({ onOpen }) {
  const filters = ["Alles", "Installatietechniek", "Elektrotechniek", "Werktuigbouw", "Opleiding"];
  const [active, setActive] = useState("Alles");
  return (
    <section data-vacancies style={{ background: "var(--ink-50)", padding: "90px 32px" }}>
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 20 }}>
          <div>
            <Eyebrow>Open posities</Eyebrow>
            <h2 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
              fontSize: 44, lineHeight: 1, letterSpacing: "-.01em", color: "#000", margin: "12px 0 0" }}>
              Vind jouw <span style={{ color: "var(--orange-500)" }}>volgende stap</span>
            </h2>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {filters.map(f => (
              <button key={f} onClick={() => setActive(f)} style={{
                fontFamily: "var(--font-body)", fontSize: 12, textTransform: "uppercase",
                letterSpacing: ".05em", padding: "9px 15px", borderRadius: 999, cursor: "pointer",
                border: active === f ? "1.3px solid #000" : "1.3px solid var(--ink-200)",
                background: active === f ? "#000" : "#fff", color: active === f ? "#fff" : "var(--ink-500)",
              }}>{f}</button>
            ))}
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 22, marginTop: 40 }}>
          {VACANCIES.map(v => <VacancyCard key={v.id} v={v} onOpen={onOpen} />)}
        </div>
      </div>
    </section>
  );
}

function EmployerBand({ }) {
  return (
    <section style={{ background: "#000", color: "#fff", padding: "84px 32px" }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", display: "flex", justifyContent: "space-between",
        alignItems: "center", gap: 40, flexWrap: "wrap" }}>
        <div style={{ maxWidth: 620 }}>
          <Eyebrow>Voor werkgevers</Eyebrow>
          <h2 style={{ fontFamily: "var(--font-display)", textTransform: "uppercase", color: "#fff",
            fontSize: 42, lineHeight: 1, letterSpacing: "-.01em", margin: "14px 0 0" }}>
            Op zoek naar <span style={{ color: "var(--orange-500)" }}>technisch talent?</span>
          </h2>
          <p style={{ fontFamily: "var(--font-body)", fontSize: 17, lineHeight: 1.55,
            color: "var(--ink-300)", marginTop: 16 }}>
            Wij leveren gemotiveerde vakspecialisten met landelijke dekking. Van detachering
            tot werving en internationaal personeel.
          </p>
        </div>
        <Button variant="primary" size="lg" icon="arrow-right">Neem contact op</Button>
      </div>
    </section>
  );
}

Object.assign(window, { VACANCIES, Hero, Manifesto, Vacancies, EmployerBand, VacancyCard });
