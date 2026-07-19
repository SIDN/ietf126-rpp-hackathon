import { type FormEvent, useEffect, useState } from "react";
import { api, type Domain, type Entry } from "./api";
import "./App.css";

function App() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [domains, setDomains] = useState<Domain[]>([]);
  const [domainsLoading, setDomainsLoading] = useState(true);
  const [domainsError, setDomainsError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadEntries = async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await api.listEntries());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load entries");
    } finally {
      setLoading(false);
    }
  };

  const loadDomains = async () => {
    setDomainsLoading(true);
    setDomainsError(null);
    try {
      setDomains(await api.listDomains());
    } catch (err) {
      setDomainsError(
        err instanceof Error ? err.message : "Failed to load domains",
      );
    } finally {
      setDomainsLoading(false);
    }
  };

  useEffect(() => {
    loadEntries();
    loadDomains();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      await api.createEntry({
        name: name.trim(),
        description: description.trim(),
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
      setName("");
      setDescription("");
      setTags("");
      await loadEntries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create entry");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api.deleteEntry(id);
      setEntries((current) => current.filter((entry) => entry.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entry");
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>Registry</h1>
        <p>A simple registry of named entries, backed by a FastAPI service.</p>
      </header>

      <main className="layout">
        <section className="panel">
          <h2>Add entry</h2>
          <form className="entry-form" onSubmit={handleSubmit}>
            <label htmlFor="name">Name</label>
            <input
              id="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. example.com"
              required
            />

            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional description"
              rows={3}
            />

            <label htmlFor="tags">Tags</label>
            <input
              id="tags"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="comma, separated, tags"
            />

            <button type="submit" disabled={submitting}>
              {submitting ? "Adding..." : "Add entry"}
            </button>
          </form>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Entries</h2>
            <button type="button" className="ghost" onClick={loadEntries}>
              Refresh
            </button>
          </div>

          {error && <p className="error">{error}</p>}
          {loading ? (
            <p>Loading...</p>
          ) : entries.length === 0 ? (
            <p className="empty">No entries yet. Add the first one.</p>
          ) : (
            <ul className="entry-list">
              {entries.map((entry) => (
                <li key={entry.id} className="entry-card">
                  <div className="entry-card-header">
                    <h3>{entry.name}</h3>
                    <button
                      type="button"
                      className="ghost danger"
                      onClick={() => handleDelete(entry.id)}
                    >
                      Delete
                    </button>
                  </div>
                  {entry.description && <p>{entry.description}</p>}
                  {entry.tags.length > 0 && (
                    <div className="tags">
                      {entry.tags.map((tag) => (
                        <span key={tag} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <section className="panel domains-panel">
        <div className="panel-header">
          <h2>Domains</h2>
          <button type="button" className="ghost" onClick={loadDomains}>
            Refresh
          </button>
        </div>
        <p className="panel-subtitle">
          Domain names tracked by the registry and the registrar currently
          sponsoring each one. Managed by registrar apps via the transfer API.
        </p>

        {domainsError && <p className="error">{domainsError}</p>}
        {domainsLoading ? (
          <p>Loading...</p>
        ) : domains.length === 0 ? (
          <p className="empty">No domains registered yet.</p>
        ) : (
          <table className="domain-table">
            <thead>
              <tr>
                <th>Domain</th>
                <th>Sponsoring registrar</th>
                <th>Last updated</th>
              </tr>
            </thead>
            <tbody>
              {domains.map((domain) => (
                <tr key={domain.name}>
                  <td>{domain.name}</td>
                  <td>{domain.registrar}</td>
                  <td>{new Date(domain.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default App;
