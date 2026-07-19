const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8001/api";
// The registrar backend, not the browser, talks to the OAuth2 provider -
// it owns the client secret. The browser only ever holds an HttpOnly
// session cookie set by the backend after a successful login.
const BACKEND_ORIGIN = API_BASE.replace(/\/api\/?$/, "");

export interface SessionInfo {
  authenticated: boolean;
  email?: string | null;
  username?: string | null;
  name?: string | null;
}

export async function getSession(): Promise<SessionInfo> {
  try {
    const res = await fetch(`${API_BASE}/auth/session`, {
      credentials: "include",
    });
    if (!res.ok) return { authenticated: false };
    return (await res.json()) as SessionInfo;
  } catch {
    return { authenticated: false };
  }
}

/** Full-page navigation to the backend, which redirects to the OAuth2
 * provider's login page. */
export function login(): void {
  window.location.href = `${BACKEND_ORIGIN}/api/auth/login`;
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}
