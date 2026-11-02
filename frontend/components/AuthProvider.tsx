"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, AUTH_EXPIRED_EVENT } from "@/lib/api";
import type { Role, User } from "@/lib/types";

interface AuthContextValue { user: User | null; loading: boolean; refresh: () => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthContextValue | null>(null);

export function authenticatedLanding(user: User) {
  return user.role === "student" && user.must_change_password ? "/student/change-password" : `/${user.role}`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();
  const refresh = async () => {
    try { setUser((await api<{user: User}>("/auth/me")).user); }
    catch { setUser(null); }
    finally { setLoading(false); }
  };
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    const expired = () => { setUser(null); setLoading(false); };
    window.addEventListener(AUTH_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired);
  }, []);
  const logout = async () => { await api<void>("/auth/logout", { method: "POST" }).catch(() => undefined); setUser(null); router.replace("/"); };
  useEffect(() => { if (!loading && !user && pathname !== "/") router.replace("/"); }, [loading, user, pathname, router]);
  return <AuthContext.Provider value={{user, loading, refresh, logout}}>{children}</AuthContext.Provider>;
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("AuthProvider missing"); return value; }
export function RoleGate({ role, children }: { role: Role; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const passwordChangeRequired = Boolean(user?.role === "student" && user.must_change_password && pathname !== "/student/change-password");
  useEffect(() => {
    if (loading || !user) return;
    if (user.role !== role || passwordChangeRequired) router.replace(authenticatedLanding(user));
  }, [loading, user, role, passwordChangeRequired, router]);
  if (loading || !user || user.role !== role || passwordChangeRequired) return <main className="center"><p>Loading secure workspace...</p></main>;
  return <>{children}</>;
}
