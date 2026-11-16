/* About page. Sections marked PENDING wait for the groupmate's text. */
export default function AboutPage() {
  return (
    <main className="about-page">
      <h1>About Lake Breathing</h1>

      <section aria-labelledby="solution-h">
        <h2 id="solution-h">Proposed solution</h2>
        <p>PENDING: groupmate's text.</p>
      </section>

      <section aria-labelledby="forecast-h">
        <h2 id="forecast-h">5-day forecast</h2>
        <p>
          The Low, Watch and High levels come from a simple rule, not a trained model. The 5-day forecast is
          different: a small model predicts each zone's algae reading from its past readings and Open-Meteo's
          weather forecast. We test it on past dates it was not trained on and compare it with assuming no change.
        </p>
      </section>

      <section aria-labelledby="future-h">
        <h2 id="future-h">Future development</h2>
        <p>PENDING: groupmate's text.</p>
      </section>

      <section aria-labelledby="limits-h">
        <h2 id="limits-h">Limits</h2>
        <ul>
          <li>The forecast depends on Open-Meteo's weather forecast.</li>
        </ul>
      </section>
    </main>
  );
}
