/* Maintec Website UI Kit — App shell & routing */

function App() {
  const [route, setRoute] = useState({ name: "home" });

  const scrollTop = () => { const el = document.querySelector("[data-scroll]"); if (el) el.scrollTop = 0; };
  const goHome = () => { setRoute({ name: "home" }); requestAnimationFrame(scrollTop); };
  const openVacancy = (v) => { setRoute({ name: "vacancy", v }); requestAnimationFrame(scrollTop); };
  const scrollToVacancies = () => {
    const scroller = document.querySelector("[data-scroll]");
    const target = document.querySelector("[data-vacancies]");
    if (scroller && target) scroller.scrollTo({ top: target.offsetTop - 76, behavior: "smooth" });
  };

  return (
    <div data-scroll style={{ height: "100vh", overflowY: "auto", background: "#fff" }}>
      <Header onHome={goHome} dark={route.name === "home" || route.name === "vacancy"} />
      {route.name === "home" && (
        <>
          <Hero onCta={scrollToVacancies} />
          <Manifesto />
          <Vacancies onOpen={openVacancy} />
          <EmployerBand />
        </>
      )}
      {route.name === "vacancy" && <VacancyDetail v={route.v} onBack={goHome} />}
      <Footer />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
