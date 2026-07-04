/* Maintec — The Future Techforce
   Recruitment site, recreated from the Maintec design system.
   Vanilla JS: routing (home <-> vacancy), sticky-header scroll state,
   vacancy filters, and the apply flow. */

(function () {
  "use strict";

  /* ---------------- Data ---------------- */
  const VACANCIES = [
    { id: 1, title: "Monteur Zonnepanelen",       region: "Utrecht",    hours: "38 uur",    type: "Fulltime", field: "Installatietechniek",  img: "assets/img/worker-duct-install.jpg",     salary: "€2.800 – €3.600" },
    { id: 2, title: "Onderhoudsmonteur",          region: "Amersfoort", hours: "40 uur",    type: "Fulltime", field: "Werktuigbouw",         img: "assets/img/workers-pipes-trio.jpg",      salary: "€2.900 – €3.800" },
    { id: 3, title: "Eerste Monteur Elektra",     region: "Nijmegen",   hours: "36 uur",    type: "Fulltime", field: "Elektrotechniek",      img: "assets/img/workers-electrical-panel.jpg", salary: "€3.100 – €4.200" },
    { id: 4, title: "Servicetechnicus",           region: "Den Bosch",  hours: "40 uur",    type: "Fulltime", field: "Service & Onderhoud",  img: "assets/img/worker-laptop-hallway.jpg",   salary: "€2.700 – €3.900" },
    { id: 5, title: "Werkvoorbereider Techniek",  region: "Eindhoven",  hours: "32–40 uur", type: "Parttime", field: "Engineering",          img: "assets/img/worker-smiling-laptop.jpg",   salary: "€3.400 – €4.500" },
    { id: 6, title: "Leerling Installatietechniek", region: "Landelijk", hours: "40 uur",   type: "Opleiding", field: "Reskilling",           img: "assets/img/workers-pipes-trio.jpg",      salary: "Opleiding + salaris" },
  ];

  // Map each vacancy field to a top-level filter bucket.
  const FILTERS = ["Alles", "Installatietechniek", "Elektrotechniek", "Werktuigbouw", "Opleiding"];
  function matchesFilter(v, f) {
    if (f === "Alles") return true;
    if (f === "Opleiding") return v.type === "Opleiding" || v.field === "Reskilling";
    return v.field === f;
  }

  /* ---------------- Tiny DOM helpers ---------------- */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        const val = attrs[k];
        if (k === "class") node.className = val;
        else if (k === "style") node.setAttribute("style", val);
        else if (k === "html") node.innerHTML = val;
        else if (k.slice(0, 2) === "on" && typeof val === "function") node.addEventListener(k.slice(2), val);
        else if (val != null) node.setAttribute(k, val);
      }
    }
    appendChildren(node, children);
    return node;
  }
  function appendChildren(node, children) {
    if (children == null) return;
    if (Array.isArray(children)) children.forEach(function (c) { appendChildren(node, c); });
    else if (typeof children === "string") node.appendChild(document.createTextNode(children));
    else node.appendChild(children);
  }
  function icon(name, size, stroke) {
    const span = el("span", { class: "icon", style: (size ? "font-size:" + size + "px;" : "") + (stroke ? "--lucide-stroke:" + stroke : "") });
    const i = document.createElement("i");
    i.setAttribute("data-lucide", name);
    if (stroke) i.setAttribute("stroke-width", stroke);
    span.appendChild(i);
    return span;
  }

  /* ---------------- Primitives ---------------- */
  function button(label, opts) {
    opts = opts || {};
    const cls = ["btn", "btn-" + (opts.variant || "primary")];
    if (opts.size === "lg") cls.push("btn-lg");
    if (opts.size === "sm") cls.push("btn-sm");
    if (opts.block) cls.push("btn-block");
    const b = el("button", { class: cls.join(" "), type: opts.type || "button", style: opts.style || "" },
      [document.createTextNode(label), opts.icon ? icon(opts.icon, opts.size === "lg" ? 18 : 16) : null]);
    if (opts.onClick) b.addEventListener("click", opts.onClick);
    return b;
  }
  function tag(label, variant) {
    return el("span", { class: "tag tag-" + (variant || "out") }, label);
  }
  function eyebrow(text) { return el("div", { class: "eyebrow" }, text); }
  function bracket(inner, brSize) {
    return el("span", { class: "bracket" }, [
      el("span", { class: "br", style: brSize ? "font-size:" + brSize + "px" : "" }, "["),
      inner,
      el("span", { class: "br", style: brSize ? "font-size:" + brSize + "px" : "" }, "]"),
    ]);
  }
  // Headline with an orange accent word/segment.
  function display(level, before, accent, after, cls) {
    const h = el(level, { class: "display " + (cls || "") });
    appendChildren(h, before);
    if (accent) h.appendChild(el("span", { class: "accent" }, accent));
    appendChildren(h, after);
    return h;
  }

  /* ---------------- Header ---------------- */
  function header(ctx) {
    const nav = ["Vacatures", "Over ons", "Voor werkgevers", "Opleidingen", "Contact"];
    const h = el("header", { class: "header" + (ctx.dark ? " on-dark" : "") }, [
      el("div", { class: "container" }, [
        el("div", { class: "header__logo", onclick: ctx.goHome }, [
          el("img", { class: "logo-black", src: "assets/logo/logo-maintec-black.svg", alt: "Maintec — The Future Techforce" }),
          el("img", { class: "logo-white", src: "assets/logo/logo-maintec-white.svg", alt: "Maintec — The Future Techforce" }),
        ]),
        el("nav", { class: "header__nav" }, nav.map(function (n, i) {
          return el("a", { onclick: i === 0 ? ctx.goHome : undefined }, n);
        })),
        button("Solliciteer", { variant: "primary", size: "sm", icon: "arrow-right", onClick: ctx.goHome }),
        el("button", { class: "menu-toggle", "aria-label": "Menu" }, icon("menu", 26)),
      ]),
    ]);
    return h;
  }

  /* ---------------- Footer ---------------- */
  function footer() {
    const cols = [
      { h: "Maintec", links: ["Over ons", "Onze visie", "Werken bij", "Nieuws", "Contact"] },
      { h: "Voor talent", links: ["Vacatures", "Opleidingen", "Reskilling", "Mijn Maintec"] },
      { h: "Voor werkgevers", links: ["Detachering", "Werving", "Internationaal", "Offerte"] },
    ];
    return el("footer", { class: "footer" }, [
      el("div", { class: "container" }, [
        el("div", { class: "footer__grid" }, [
          el("div", {}, [
            el("div", { class: "footer__logo" }, el("img", { src: "assets/logo/logo-maintec-white.svg", alt: "Maintec — The Future Techforce" })),
            el("p", { class: "footer__about" }, "Een collectief van gemotiveerde vakprofessionals binnen de techniek. Wij zijn werkgever — onze mensen zijn collega's."),
            el("div", { class: "footer__social" }, ["linkedin", "instagram", "facebook"].map(function (s) {
              return el("span", { "aria-label": s }, icon(s, 18));
            })),
          ]),
          cols.map(function (c) {
            return el("div", { class: "footer__col" }, [
              el("h4", {}, c.h),
              el("div", { class: "links" }, c.links.map(function (l) { return el("a", {}, l); })),
            ]);
          }),
        ]),
        el("div", { class: "footer__bottom" }, [
          bracket(el("span", { class: "tagline" }, "The Future Techforce"), 20),
          el("div", { class: "footer__copy" }, "© 2026 Maintec · onderdeel van TecqGroep · Privacy · Voorwaarden"),
        ]),
      ]),
    ]);
  }

  /* ---------------- Home sections ---------------- */
  function hero(ctx) {
    return el("section", { class: "hero" }, [
      el("div", { class: "hero__photo" }),
      el("div", { class: "hero__scrim" }),
      el("div", { class: "container hero__inner" }, [
        el("div", { class: "hero__copy" }, [
          eyebrow("Werken bij Maintec"),
          display("h1", "Hallo ", "collega"),
          el("p", { class: "hero__lead" }, "Jij kan meer uit je werk halen dan je denkt. Sluit je aan bij een werkgever die verder kijkt dan vandaag. Laten we samen onze krachten bundelen."),
          el("div", { class: "hero__actions" }, [
            button("Bekijk vacatures", { variant: "primary", size: "lg", icon: "arrow-right", onClick: ctx.scrollToVacancies }),
            button("Ons verhaal", { variant: "outline", size: "lg", style: "color:#fff" }),
          ]),
        ]),
      ]),
      el("div", { class: "hero__tagline" }, [
        el("div", { class: "container" }, [
          display("span", "Join the future ", "techforce"),
        ]),
      ]),
    ]);
  }

  function manifesto() {
    const pillars = [
      ["users", "Hecht team", "Een collectief van collega's, geen losse flexkrachten."],
      ["graduation-cap", "Eigen vakschool", "Opleiding, reskilling én upskilling van technisch talent."],
      ["shield-check", "Echt werkgeverschap", "Vaste begeleiding, goede arbeidsvoorwaarden, aandacht."],
    ];
    return el("section", { class: "manifesto" }, [
      el("div", { class: "inner" }, [
        eyebrow("Merkverhaal"),
        el("h2", { class: "display" }, [
          document.createTextNode("Wij zijn een collectief van"),
          el("br"),
          el("span", { class: "accent" }, "gemotiveerde vakspecialisten"),
        ]),
        el("p", { class: "manifesto__lead" }, "Zie ons niet als het zoveelste uitzendbureau of detacheerder. Wij zijn op de eerste plaats werkgever. Onze mensen zijn geen 'kandidaten' — ze zijn collega's. Wij begrijpen de wereld van techniek als geen ander, want we zitten er middenin."),
        el("div", { class: "pillars" }, pillars.map(function (p) {
          return el("div", { class: "pillar" }, [
            el("span", { class: "pillar__icon" }, icon(p[0], 26)),
            el("h3", {}, p[1]),
            el("p", {}, p[2]),
          ]);
        })),
      ]),
    ]);
  }

  function vacancyCard(v, ctx) {
    return el("div", { class: "vcard", onclick: function () { ctx.openVacancy(v); } }, [
      el("div", { class: "vcard__photo", style: "background-image:url(" + v.img + ")" }, [
        el("div", { class: "vcard__tag" }, tag(v.type, "orange")),
      ]),
      el("div", { class: "vcard__body" }, [
        el("div", { class: "vcard__field" }, v.field),
        el("div", { class: "vcard__title" }, v.title),
        el("div", { class: "vcard__meta" }, [
          el("span", {}, [icon("map-pin", 15), document.createTextNode(v.region)]),
          el("span", {}, [icon("clock", 15), document.createTextNode(v.hours)]),
        ]),
      ]),
    ]);
  }

  function vacancies(ctx) {
    let active = "Alles";
    const grid = el("div", { class: "vacancy-grid" });
    const filterRow = el("div", { class: "filters" });

    function renderGrid() {
      grid.innerHTML = "";
      VACANCIES.filter(function (v) { return matchesFilter(v, active); })
        .forEach(function (v) { grid.appendChild(vacancyCard(v, ctx)); });
      window.lucide && window.lucide.createIcons();
    }
    function renderFilters() {
      filterRow.innerHTML = "";
      FILTERS.forEach(function (f) {
        filterRow.appendChild(el("button", {
          class: "filter" + (f === active ? " active" : ""),
          onclick: function () { active = f; renderFilters(); renderGrid(); },
        }, f));
      });
    }
    renderFilters();
    renderGrid();

    return el("section", { class: "vacancies", "data-vacancies": "" }, [
      el("div", { class: "container" }, [
        el("div", { class: "vacancies__head" }, [
          el("div", {}, [
            eyebrow("Open posities"),
            display("h2", "Vind jouw ", "volgende stap"),
          ]),
          filterRow,
        ]),
        grid,
      ]),
    ]);
  }

  function employerBand() {
    return el("section", { class: "employer" }, [
      el("div", { class: "container" }, [
        el("div", { class: "employer__copy" }, [
          eyebrow("Voor werkgevers"),
          display("h2", "Op zoek naar ", "technisch talent?"),
          el("p", { class: "employer__lead" }, "Wij leveren gemotiveerde vakspecialisten met landelijke dekking. Van detachering tot werving en internationaal personeel."),
        ]),
        button("Neem contact op", { variant: "primary", size: "lg", icon: "arrow-right" }),
      ]),
    ]);
  }

  /* ---------------- Vacancy detail ---------------- */
  function vacancyDetail(v, ctx) {
    const benefits = [
      "Vast dienstverband bij Maintec — jij bent collega, geen kandidaat",
      "Persoonlijke begeleiding door een vaste consultant",
      "Toegang tot onze eigen vakschool: reskilling & upskilling",
      "Werken met topmateriaal bij de gaafste technische bedrijven",
    ];
    const meta = [["map-pin", v.region], ["clock", v.hours], ["wallet", v.salary], ["briefcase", v.type]];

    const applyCard = el("div", { class: "apply-card" });
    function renderForm() {
      applyCard.innerHTML = "";
      appendChildren(applyCard, [
        eyebrow("Solliciteer direct"),
        el("div", { class: "title" }, "Word collega"),
        ["Naam", "E-mailadres", "Telefoon"].map(function (l) {
          return el("div", { class: "field" }, [
            el("label", {}, l),
            el("input", { type: l === "E-mailadres" ? "email" : l === "Telefoon" ? "tel" : "text" }),
          ]);
        }),
        el("div", { style: "margin-top:8px" }, button("Verstuur sollicitatie", {
          variant: "primary", icon: "arrow-right", block: true, onClick: renderSuccess,
        })),
        el("p", { class: "note" }, "Of bel ons direct — we denken graag met je mee."),
      ]);
      window.lucide && window.lucide.createIcons();
    }
    function renderSuccess() {
      applyCard.innerHTML = "";
      appendChildren(applyCard, el("div", { class: "apply-success" }, [
        el("div", { class: "check" }, icon("check", 30, 3)),
        el("div", { class: "title" }, "Welkom collega!"),
        el("p", {}, "We hebben je sollicitatie ontvangen en nemen snel contact met je op."),
      ]));
      window.lucide && window.lucide.createIcons();
    }
    renderForm();

    return el("div", {}, [
      el("section", { class: "detail-hero" }, [
        el("div", { class: "detail-hero__photo", style: "background-image:url(" + v.img + ")" }),
        el("div", { class: "detail-hero__scrim" }),
        el("div", { class: "container detail-hero__inner" }, [
          el("button", { class: "back-link", onclick: ctx.goHome }, [icon("arrow-left", 16), document.createTextNode("Terug naar vacatures")]),
          el("div", { class: "detail-hero__tags" }, [tag(v.type, "orange"), tag(v.field, "dark")]),
          el("h1", {}, v.title),
          el("div", { class: "detail-hero__meta" }, meta.map(function (m) {
            return el("span", {}, [icon(m[0], 17), document.createTextNode(m[1])]);
          })),
        ]),
      ]),
      el("section", { class: "detail-body" }, [
        el("div", { class: "container" }, [
          el("div", { class: "grid" }, [
            el("div", {}, [
              el("h3", {}, "Over de functie"),
              el("p", { class: "lead" }, "Als " + v.title.toLowerCase() + " werk je samen met een hecht team aan uitdagende projecten in de " + v.field.toLowerCase() + ". Je krijgt de beste begeleiding die je maar kunt wensen en de ruimte om jezelf te blijven ontwikkelen. Bij Maintec sta je er nooit alleen voor — we bundelen onze krachten."),
              el("h3", { class: "spaced" }, "Wat wij bieden"),
              el("div", { class: "benefits" }, benefits.map(function (b) {
                return el("div", { class: "benefit" }, [
                  icon("check", 20, 2.6),
                  el("span", {}, b),
                ]);
              })),
            ]),
            el("div", { class: "apply-card-wrap" }, applyCard),
          ]),
        ]),
      ]),
    ]);
  }

  /* ---------------- App / routing ---------------- */
  const root = document.getElementById("root");
  let scroller = null;
  let route = { name: "home" };

  function scrollTop() { if (scroller) scroller.scrollTop = 0; }

  const ctx = {
    dark: true,
    goHome: function () { route = { name: "home" }; render(); requestAnimationFrame(scrollTop); },
    openVacancy: function (v) { route = { name: "vacancy", v: v }; render(); requestAnimationFrame(scrollTop); },
    scrollToVacancies: function () {
      const target = document.querySelector("[data-vacancies]");
      if (scroller && target) scroller.scrollTo({ top: target.offsetTop - 76, behavior: "smooth" });
    },
  };

  function render() {
    root.innerHTML = "";
    scroller = el("div", { "data-scroll": "", style: "height:100vh;overflow-y:auto;background:#fff" });

    const head = header(ctx);
    scroller.appendChild(head);

    if (route.name === "home") {
      appendChildren(scroller, [hero(ctx), manifesto(), vacancies(ctx), employerBand()]);
    } else if (route.name === "vacancy") {
      scroller.appendChild(vacancyDetail(route.v, ctx));
    }
    scroller.appendChild(footer());
    root.appendChild(scroller);

    // sticky header: transparent over dark hero, solid once scrolled
    function onScroll() {
      if (scroller.scrollTop > 40) head.classList.remove("on-dark");
      else head.classList.add("on-dark");
    }
    head.classList.add("on-dark");
    scroller.addEventListener("scroll", onScroll);

    window.lucide && window.lucide.createIcons();
  }

  render();
})();
