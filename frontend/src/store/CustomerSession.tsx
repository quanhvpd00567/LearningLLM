import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { shopApi } from "./api";

export type Customer = { id: string; name: string; email: string };
const Context = createContext<{ user: Customer | null; loading: boolean; error: string; refresh: () => void }>({ user: null, loading: true, error: "", refresh: () => {} });
export const useCustomer = () => useContext(Context);
export function CustomerProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    shopApi<Customer>("/auth/me").then(value => { if (alive) { setUser(value); setError(""); } })
      .catch(e => { if (alive) { setUser(null); setError(e.status === 401 ? "" : e.message); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [revision]);
  useEffect(() => {
    const expired = () => { setUser(null); };
    const changed = (event: StorageEvent) => { if (event.key === "customer-auth-changed") location.reload(); };
    const focus = () => setRevision(v => v + 1);
    window.addEventListener("customer-session-expired", expired);
    window.addEventListener("storage", changed);
    window.addEventListener("focus", focus);
    return () => { window.removeEventListener("customer-session-expired", expired); window.removeEventListener("storage", changed); window.removeEventListener("focus", focus); };
  }, []);
  return <Context.Provider value={{ user, loading, error, refresh: () => setRevision(v => v + 1) }}>{children}</Context.Provider>;
}
export function notifyCustomerChange() {
  try { localStorage.setItem("customer-auth-changed", String(Date.now())); } catch { /* Cookies remain the source of identity. */ }
}
export function signIn(next = "account") { location.assign("/login?next=" + encodeURIComponent(next)); }
