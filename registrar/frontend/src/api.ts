export interface Domain {
  name: string;
  registrar: string;
  created_at: string;
  updated_at: string;
}

export interface DomainAuthInfo {
  name: string;
  transfer_token: string;
}

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8001/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getMe: () => request<{ registrar_name: string }>("/me"),
  listMyDomains: () => request<Domain[]>("/domains"),
  getTransferToken: (domainName: string) =>
    request<DomainAuthInfo>(`/domains/${encodeURIComponent(domainName)}/transfer-token`),
  /** Full-page URL to kick off a cross-registrar transfer authorization
   * redirect (see backend api/transfer_routes.py). Navigate the browser
   * here directly - do not `fetch()` it. */
  transferStartUrl: (domainName: string) =>
    `${API_BASE}/transfer/start?${new URLSearchParams({ domain: domainName })}`,
  /** Full-page URL to submit the domain owner's approve/cancel decision
   * on a pending transfer-authorization consent screen. Navigate the
   * browser here directly - do not `fetch()` it. */
  transferDecisionUrl: (
    consent: { domain: string; registrar: string; returnUrl: string },
    approved: boolean,
  ) =>
    `${API_BASE}/transfer/decision?${new URLSearchParams({
      domain: consent.domain,
      registrar: consent.registrar,
      return_url: consent.returnUrl,
      approved: String(approved),
    })}`,
};
