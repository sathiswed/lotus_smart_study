"use client";

import { FormEvent, useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { authenticatedLanding, useAuth } from "@/components/AuthProvider";
import { Notice } from "@/components/Ui";

export default function LoginPage() {
  const [loginIdentifier,setLoginIdentifier]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  const {user,refresh,loading}=useAuth(); const router=useRouter();
  useEffect(()=>{ if(!loading && user) router.replace(authenticatedLanding(user)); },[user,loading,router]);
  async function submit(event:FormEvent){ event.preventDefault(); setBusy(true); setError(""); try { const result=await api<{user:User}>("/auth/login",{method:"POST",body:JSON.stringify({login_identifier:loginIdentifier,password})}); await refresh(); router.replace(authenticatedLanding(result.user)); } catch(error){ setError(error instanceof Error?error.message:"Unable to sign in"); } finally {setBusy(false);} }
  return <main className="login-page"><section className="login-card"><div className="login-brand"><Image src="/lotus_logo_new.png" alt="Lotus Smart Study - Learn, Think, Grow" width={300} height={200} className="login-logo" priority /></div><div className="login-content"><p className="eyebrow">Textbook-grounded assessment</p><h1>Welcome back</h1><p className="muted">Sign in to continue to your teacher or student workspace.</p>{error&&<Notice kind="error">{error}</Notice>}<form onSubmit={submit} className="stack login-form"><label>Email or login ID<input autoComplete="username" required value={loginIdentifier} onChange={e=>setLoginIdentifier(e.target.value)} placeholder="Enter your email or login ID"/></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password"/></label><button disabled={busy}>{busy?"Signing in...":"Sign in securely"}</button></form><p className="login-footnote">Teacher-controlled assessments | Secure student access</p></div></section></main>;
}
