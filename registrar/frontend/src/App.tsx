import { type FormEvent, useEffect, useState } from "react";
import { api, type Domain } from "./api";
import { getSession, login, logout, type SessionInfo } from "./auth";
import "./App.css";

function App() {
  const [registrarName, setRegistrarName] = useState<string | null>(null);

  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [session, setSession] = useState<SessionInfo>({ authenticated: false });
  const [authLoading, setAuthLoading] = useState(true);

  const [pullDomainName, setPullDomainName] = useState("");
  const [successDomain, setSuccessDomain] = useState<string | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  const [consent, setConsent] = useState<
    { domain: string; registrar: string; returnUrl: string } | null
  >(null);

  const [revealingDomain, setRevealingDomain] = useState<string | null>(null);
  const [revealedTokens, setRevealedTokens] = useState<Record<string, string>>(
    {},
  );
  const [revealError, setRevealError] = useState<string | null>(null);

  const [copiedDomain, setCopiedDomain] = useState<string | null>(null);

  const loadDomains = async () => {
    setLoading(true);
    setError(null);
    try {
      const [me, myDomains] = await Promise.all([
        api.getMe(),
        api.listMyDomains(),
      ]);
      setRegistrarName(me.registrar_name);
      setDomains(myDomains);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load domains");
    } finally {
      setLoading(false);
    }
  };

  const loadSession = async () => {
    setAuthLoading(true);
    setSession(await getSession());
    setAuthLoading(false);
  };

  useEffect(() => {
    loadDomains();
    loadSession();

    const params = new URLSearchParams(window.location.search);

    // The losing registrar's /transfer/authorize redirects here to show a
    // consent screen before approving/cancelling a pending transfer.
    const consentDomain = params.get("domain");
    const consentRegistrar = params.get("registrar");
    const consentReturnUrl = params.get("return_url");
    if (
      params.get("transfer_consent") === "1" &&
      consentDomain &&
      consentRegistrar &&
      consentReturnUrl
    ) {
      setConsent({ domain: consentDomain, registrar: consentRegistrar, returnUrl: consentReturnUrl });
      window.history.replaceState({}, "", window.location.pathname);
      return;
    }

    // After the cross-registrar transfer-authorization redirect chain
    // completes, the backend lands us back here with a result in the URL.
    // Just remember the transferred domain name here - `registrarName`
    // itself is still null at this point (loadDomains() hasn't resolved
    // yet), so the message is composed at render time below instead.
    const success = params.get("transfer_success");
    const failure = params.get("transfer_error");
    if (success) {
      setSuccessDomain(success);
    }
    if (failure) {
      setPullError(failure);
    }
    if (success || failure) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = async () => {
    await logout();
    setSession({ authenticated: false });
  };

  const handlePullSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pullDomainName.trim() || !session.authenticated) return;

    // Full-page navigation: the backend redirects the browser to the
    // losing registrar's authorization endpoint, which (after the domain
    // owner authorizes there) redirects to the registry's fixed callback,
    // which redirects back to this registrar's /transfer/complete, which
    // finally lands back here with a transfer_success/transfer_error param.
    window.location.href = api.transferStartUrl(pullDomainName.trim());
  };

  const handleReveal = async (domainName: string) => {
    setRevealingDomain(domainName);
    setRevealError(null);
    try {
      const authInfo = await api.getTransferToken(domainName);
      setRevealedTokens((current) => ({
        ...current,
        [domainName]: authInfo.transfer_token,
      }));
    } catch (err) {
      setRevealError(
        err instanceof Error ? err.message : "Failed to reveal transfer token",
      );
    } finally {
      setRevealingDomain(null);
    }
  };

  const handleApproveTransfer = () => {
    if (!consent) return;
    window.location.href = api.transferDecisionUrl(consent, true);
  };

  const handleCancelTransfer = () => {
    if (!consent) return;
    window.location.href = api.transferDecisionUrl(consent, false);
  };

  const handleCopyDomain = async (domainName: string) => {
    try {
      await navigator.clipboard.writeText(domainName);
      setCopiedDomain(domainName);
      setTimeout(() => {
        setCopiedDomain((current) => (current === domainName ? null : current));
      }, 1500);
    } catch {
      // Clipboard access can fail (e.g. insecure context or denied
      // permission) - just silently ignore, there's no destructive effect.
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <div className="page-header-row">
          <div className="page-header-title">
            <h1>{registrarName} Portal</h1>
          </div>
          <div className="auth-status">
            {authLoading ? (
              <span className="muted-small">Checking login...</span>
            ) : session.authenticated ? (
              <>
                <span className="muted-small">
                  Logged in as{" "}
                  {session.name ?? session.email ?? session.username ?? "user"}
                </span>
                <button type="button" className="ghost" onClick={handleLogout}>
                  Sign out
                </button>
              </>
            ) : (
              <button type="button" className="ghost" onClick={login}>
                Sign in
              </button>
            )}
          </div>
        </div>
      </header>

      {consent ? (
        <main className="layout">
          <section className="panel">
            <h2>Approve domain transfer</h2>
            <p className="panel-subtitle">
              <strong>{consent.registrar}</strong> wants to transfer{" "}
              <strong>{consent.domain}</strong> away from{" "}
              {registrarName ?? "this registrar"}. Only approve this if you
              requested the transfer yourself.
            </p>
            <div className="entry-form">
              <button type="button" onClick={handleApproveTransfer}>
                Approve transfer
              </button>
              <button type="button" className="ghost" onClick={handleCancelTransfer}>
                Cancel transfer
              </button>
            </div>
          </section>
        </main>
      ) : (
      <main className="layout">
        <section className="panel">
          <h2>Transfer a domain</h2>
          <p className="panel-subtitle">
            Transfer a domain away from its current registrar to{" "}
            {registrarName ?? "this registrar"}. You'll be redirected to sign
            in with the domain's current (losing) registrar to authorize the
            transfer - no transfer token needed.
          </p>

          {!authLoading && !session.authenticated ? (
            <p className="empty">
              <br />
              Sign in to your account to start a transfer.
            </p>
          ) : (
            <form className="entry-form" onSubmit={handlePullSubmit}>
              <label htmlFor="pull-domain">Domain</label>
              <input
                id="pull-domain"
                value={pullDomainName}
                onChange={(event) => setPullDomainName(event.target.value)}
                placeholder="e.g. example.org"
                disabled={!session.authenticated}
                required
              />

              <button type="submit" disabled={!session.authenticated}>
                Start transfer
              </button>
            </form>
          )}

          {successDomain && (
            <p className="success">
              Transfer complete: {successDomain} is now sponsored by{" "}
              {registrarName ?? "this registrar"}.
            </p>
          )}
          {pullError && <p className="error">{pullError}</p>}
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Your domains</h2>
            <button type="button" className="ghost" onClick={loadDomains}>
              Refresh
            </button>
          </div>

          {error && <p className="error">{error}</p>}
          {revealError && <p className="error">{revealError}</p>}

          {loading ? (
            <p>Loading...</p>
          ) : domains.length === 0 ? (
            <p className="empty">No domains sponsored by this registrar.</p>
          ) : (
            <ul className="entry-list">
              {domains.map((domain) => (
                <li key={domain.name} className="entry-card">
                  <div className="entry-card-header">
                    <h3
                      className="copyable-domain"
                      role="button"
                      tabIndex={0}
                      title="Click to copy domain name"
                      onClick={() => handleCopyDomain(domain.name)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleCopyDomain(domain.name);
                        }
                      }}
                    >
                      {domain.name}
                      {copiedDomain === domain.name && (
                        <span className="copied-badge">Copied!</span>
                      )}
                    </h3>
                    <button
                      type="button"
                      className="ghost"
                      disabled={revealingDomain === domain.name}
                      onClick={() => handleReveal(domain.name)}
                    >
                      {revealingDomain === domain.name
                        ? "Revealing..."
                        : "Reveal token"}
                    </button>
                  </div>
                  <p className="muted-small">
                    Updated {new Date(domain.updated_at).toLocaleString()}
                  </p>
                  {revealedTokens[domain.name] && (
                    <p className="token-reveal">
                      Transfer token: <code>{revealedTokens[domain.name]}</code>
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
      )}
    </div>
  );
}

export default App;
