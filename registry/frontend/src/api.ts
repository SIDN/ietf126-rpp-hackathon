export interface Entry {
  id: string;
  name: string;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface EntryInput {
  name: string;
  description: string;
  tags: string[];
}

export interface Domain {
  name: string;
  registrar: string;
  created_at: string;
  updated_at: string;
}

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  listEntries: () => request<Entry[]>("/entries"),
  createEntry: (payload: EntryInput) =>
    request<Entry>("/entries", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteEntry: (id: string) =>
    request<void>(`/entries/${id}`, { method: "DELETE" }),
  listDomains: () => request<Domain[]>("/domains"),
};
