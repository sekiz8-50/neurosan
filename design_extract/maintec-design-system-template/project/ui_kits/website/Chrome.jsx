/* Maintec Website UI Kit — Header & Footer */

function Header({ onHome, dark = false }) {
  const [scrolled, setScrolled] = useState(false);
  const nav = ["Vacatures", "Over ons", "Voor werkgevers", "Opleidingen", "Contact"];
  const onDark = dark && !scrolled;
  useEffect(() => {
    const el = document.querySelector("[data-scroll]");
    if (!el) return;
    const fn = () => setScrolled(el.scrollTop > 40);
    el.addEventListener("scroll", fn);
    return () => el.removeEventListener("scroll", fn);
  }, []);
  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 50,
      background: onDark ? "transparent" : "#fff",
      borderBottom: onDark ? "1px solid rgba(255,255,255,.12)" : "1px solid var(--ink-100)",
      transition: "background .25s, border-color .25s",
    }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "0 32px", height: 76,
        display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div onClick={onHome} style={{ cursor: "pointer" }}>
          <Logo variant={onDark ? "white" : "black"} height={28} />
        </div>
        <nav style={{ display: "flex", gap: 30, alignItems: "center" }}>
          {nav.map((n, i) => (
            <a key={n} onClick={i === 0 ? onHome : undefined} style={{
              fontFamily: "var(--font-body)", fontSize: 14, cursor: "pointer",
              color: onDark ? "rgba(255,255,255,.85)" : "var(--ink-600)",
              textDecoration: "none", letterSpacing: ".01em",
            }}>{n}</a>
          ))}
        </nav>
        <Button variant="primary" size="sm" icon="arrow-right">Solliciteer</Button>
      </div>
    </header>
  );
}

function Footer() {
  const cols = [
    { h: "Maintec", links: ["Over ons", "Onze visie", "Werken bij", "Nieuws", "Contact"] },
    { h: "Voor talent", links: ["Vacatures", "Opleidingen", "Reskilling", "Mijn Maintec"] },
    { h: "Voor werkgevers", links: ["Detachering", "Werving", "Internationaal", "Offerte"] },
  ];
  return (
    <footer className="on-dark" style={{ background: "#000", color: "#fff", padding: "64px 32px 36px" }}>
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr 1fr", gap: 40, paddingBottom: 48 }}>
          <div>
            <Logo variant="white" height={30} />
            <p style={{ fontFamily: "var(--font-body)", fontSize: 14, lineHeight: 1.6,
              color: "var(--ink-300)", marginTop: 20, maxWidth: 280 }}>
              Een collectief van gemotiveerde vakprofessionals binnen de techniek.
              Wij zijn werkgever — onze mensen zijn collega's.
            </p>
            <div style={{ marginTop: 22, display: "flex", gap: 12 }}>
              {["linkedin", "instagram", "facebook"].map(s => (
                <span key={s} style={{ width: 38, height: 38, borderRadius: 4, border: "1px solid var(--ink-700)",
                  display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", cursor: "pointer" }}>
                  <Icon name={s} size={18} />
                </span>
              ))}
            </div>
          </div>
          {cols.map(c => (
            <div key={c.h}>
              <div style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
                fontSize: 15, letterSpacing: ".02em", marginBottom: 16 }}>{c.h}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
                {c.links.map(l => (
                  <a key={l} style={{ fontFamily: "var(--font-body)", fontSize: 14,
                    color: "var(--ink-300)", textDecoration: "none", cursor: "pointer" }}>{l}</a>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div style={{ borderTop: "1px solid var(--ink-700)", paddingTop: 24,
          display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Bracket color="var(--orange-500)" size={20} gap={8}>
            <span style={{ fontFamily: "var(--font-display)", textTransform: "uppercase",
              fontSize: 13, letterSpacing: ".08em", color: "#fff" }}>The Future Techforce</span>
          </Bracket>
          <div style={{ fontFamily: "var(--font-body)", fontSize: 12, color: "var(--ink-400)" }}>
            © 2026 Maintec · onderdeel van TecqGroep · Privacy · Voorwaarden
          </div>
        </div>
      </div>
    </footer>
  );
}

Object.assign(window, { Header, Footer });
