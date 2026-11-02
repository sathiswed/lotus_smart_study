"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { Notice } from "@/components/Ui";
import { api } from "@/lib/api";
import type { ChangePasswordInput, User } from "@/lib/types";

function passwordError(password: string) {
  if (password.length < 10 || password.length > 256) return "Use between 10 and 256 characters.";
  if (/\s/.test(password)) return "Do not include spaces or other whitespace.";
  if (!/[a-z]/.test(password)) return "Include at least one lowercase letter.";
  if (!/[A-Z]/.test(password)) return "Include at least one uppercase letter.";
  if (!/\d/.test(password)) return "Include at least one number.";
  if (!/[^A-Za-z0-9\s]/.test(password)) return "Include at least one symbol.";
  return "";
}

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const { user, refresh } = useAuth();
  const router = useRouter();

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    const ruleError = passwordError(newPassword);
    if (ruleError) { setError(ruleError); return; }
    if (newPassword === currentPassword) { setError("Your new password must be different from your current password."); return; }
    if (newPassword !== confirmPassword) { setError("New password and confirmation do not match."); return; }
    setBusy(true);
    try {
      const payload: ChangePasswordInput = { current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword };
      await api<{ user: User }>("/auth/change-password", { method: "POST", body: JSON.stringify(payload) });
      setSuccess("Password changed. Other active sessions have been signed out.");
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      await refresh();
      router.replace("/student");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Password could not be changed");
    } finally { setBusy(false); }
  }

  return <><div className="page-header"><div><p className="eyebrow">Account security</p><h1>Change password</h1><p className="muted">{user?.must_change_password ? "You must replace your temporary password before accessing student features." : "Choose a new password for your student account."}</p></div></div>
    <section className="card" style={{ maxWidth: "620px" }}>
      {error && <Notice kind="error">{error}</Notice>}{success && <Notice kind="success">{success}</Notice>}
      <form className="stack" onSubmit={submit}>
        <label>Current password<input type="password" autoComplete="current-password" required maxLength={256} value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} /></label>
        <label>New password<input type="password" autoComplete="new-password" required minLength={10} maxLength={256} value={newPassword} onChange={event => setNewPassword(event.target.value)} /></label>
        <label>Confirm new password<input type="password" autoComplete="new-password" required minLength={10} maxLength={256} value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} /></label>
        <div><strong>Password requirements</strong><ul className="password-rules"><li>10 to 256 characters with no whitespace</li><li>At least one lowercase letter, uppercase letter, number and symbol</li><li>Different from your current password</li></ul></div>
        <button disabled={busy}>{busy ? "Changing password..." : "Change password"}</button>
      </form>
    </section>
  </>;
}
