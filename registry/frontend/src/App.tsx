import { type FormEvent, useEffect, useState } from "react";
import { api, type Domain } from "./api";
import acmeLogo from "./assets/acme-logo.png";
import "./App.css";

function App() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [registrar, setRegistrar] = useState("");
  const [registrant, setRegistrant] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadDomains = async () => {
    setLoading(true);
    setError(null);
    try {
      setDomains(await api.listDomains());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load domains");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDomains();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim() || !registrar.trim() || !registrant.trim()) return;

    setSubmitting(true);
    setFormError(null);
    try {
      await api.createDomain({
        name: name.trim(),
        registrar: registrar.trim(),
        registrant: registrant.trim(),
      });
      setName("");
      setRegistrar("");
      setRegistrant("");
      await loadDomains();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to add domain");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <img src={acmeLogo} alt="ACME logo" className="page-logo" />
        <div>
          <h1>ACME - Registry</h1>
          <p>A simple domain name registry</p>
        </div>
      </header>

      <main className="layout">
        <section className="panel">
          <h2>New domain name</h2>
          <form className="entry-form" onSubmit={handleSubmit}>
            <label htmlFor="domain-name">Domain name</label>
            <input
              id="domain-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. example.com"
              required
            />

            <label htmlFor="registrar">Sponsoring registrar</label>
            <input
              id="registrar"
              value={registrar}
              onChange={(event) => setRegistrar(event.target.value)}
              placeholder="e.g. Registrar A"
              required
            />

            <label htmlFor="registrant">Registrant</label>
            <input
              id="registrant"
              value={registrant}
              onChange={(event) => setRegistrant(event.target.value)}
              placeholder="e.g. jane.doe"
              required
            />

            <button type="submit" disabled={submitting}>
              {submitting ? "Adding..." : "Register"}
            </button>
          </form>

          {formError && <p className="error">{formError}</p>}
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Registered Domain names</h2>
            <button type="button" className="ghost" onClick={loadDomains}>
              Refresh
            </button>
          </div>

          {error && <p className="error">{error}</p>}
          {loading ? (
            <p>Loading...</p>
          ) : domains.length === 0 ? (
            <p className="empty">No domains registered yet.</p>
          ) : (
            <table className="domain-table">
              <thead>
                <tr>
                  <th>Domain name</th>
                  <th>Registrar</th>
                  <th>Registrant</th>
                  <th>Last updated</th>
                </tr>
              </thead>
              <tbody>
                {domains.map((domain) => (
                  <tr key={domain.name}>
                    <td>{domain.name}</td>
                    <td>{domain.registrar}</td>
                    <td>{domain.registrant}</td>
                    <td>{new Date(domain.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
