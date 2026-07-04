/* Maintec Website UI Kit — shared primitives
   Loaded as a Babel script; exports components to window. */

const { useState, useEffect, useRef } = React;

/* ---------- Icon (Lucide via CDN) ---------- */
function Icon({ name, size = 20, stroke = 2, className = "", style = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.lucide && ref.current) {
      ref.current.innerHTML = "";
      const el = document.createElement("i");
      el.setAttribute("data-lucide", name);
      ref.current.appendChild(el);
      window.lucide.createIcons({
        attrs: { width: size, height: size, "stroke-width": stroke },
        nameAttr: "data-lucide",
      });
    }
  }, [name, size, stroke]);
  return <span ref={ref} className={className} style={{ display: "inline-flex", lineHeight: 0, ...style }} />;
}

/* ---------- Logo ---------- */
function Logo({ variant = "black", height = 30 }) {
  const src = variant === "white"
    ? "../../assets/logo-maintec-white.svg"
    : "../../assets/logo-maintec-black.svg";
  return <img src={src} alt="Maintec — The Future Techforce" style={{ height, display: "block" }} />;
}

/* ---------- Button ---------- */
function Button({ children, variant = "primary", size = "md", icon, onClick, type, style = {} }) {
  const base = {
    fontFamily: "var(--font-body)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontSize: size === "lg" ? 15 : size === "sm" ? 12 : 13,
    padding: size === "lg" ? "16px 28px" : size === "sm" ? "9px 16px" : "13px 22px",
    borderRadius: 4,
    border: "1.5px solid transparent",
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 9,
    transition: "background .15s, color .15s, border-color .15s",
    whiteSpace: "nowrap",
    ...style,
  };
  const variants = {
    primary: { background: "var(--orange-500)", color: "#fff" },
    dark:    { background: "#000", color: "#fff" },
    light:   { background: "#fff", color: "#000" },
    outline: { background: "transparent", color: "currentColor", borderColor: "currentColor" },
    ghost:   { background: "transparent", color: "var(--orange-500)", padding: "10px 6px" },
  };
  const [hover, setHover] = useState(false);
  const hov = {
    primary: { background: "var(--orange-600)" },
    dark:    { background: "#1c1c1d" },
    light:   { background: "#eee" },
    outline: { background: "rgba(255,125,47,.1)", borderColor: "var(--orange-500)", color: "var(--orange-500)" },
    ghost:   { color: "var(--orange-600)" },
  };
  return (
    <button type={type} onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...variants[variant], ...(hover ? hov[variant] : {}) }}>
      {children}
      {icon && <Icon name={icon} size={size === "lg" ? 18 : 16} stroke={2.4} />}
    </button>
  );
}

/* ---------- Tag ---------- */
function Tag({ children, variant = "out" }) {
  const styles = {
    orange: { background: "var(--orange-500)", color: "#fff", border: "none" },
    dark:   { background: "#000", color: "#fff", border: "none" },
    soft:   { background: "var(--orange-100)", color: "var(--orange-700)", border: "none" },
    out:    { background: "transparent", color: "var(--ink-500)", border: "1.3px solid var(--ink-200)" },
  };
  return (
    <span style={{
      fontFamily: "var(--font-body)", fontSize: 11, textTransform: "uppercase",
      letterSpacing: "0.05em", padding: "6px 12px", borderRadius: 999,
      display: "inline-flex", alignItems: "center", gap: 6, ...styles[variant],
    }}>{children}</span>
  );
}

/* ---------- Bracket device ---------- */
function Bracket({ children, color = "var(--orange-500)", size = 28, gap = 10 }) {
  const b = { color, fontWeight: 700, fontFamily: "'Arial Narrow', var(--font-display)", fontSize: size, lineHeight: 1 };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap }}>
      <span style={b}>[</span>{children}<span style={b}>]</span>
    </span>
  );
}

/* ---------- Eyebrow ---------- */
function Eyebrow({ children, color = "var(--orange-500)" }) {
  return <div style={{
    fontFamily: "var(--font-body)", fontSize: 12, textTransform: "uppercase",
    letterSpacing: "0.14em", color, fontWeight: 400,
  }}>{children}</div>;
}

Object.assign(window, { Icon, Logo, Button, Tag, Bracket, Eyebrow });
