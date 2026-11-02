"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Curriculum, ManagedStudent, StudentCredentials, StudentListResponse, StudentStatus } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

const PAGE_SIZE = 25;
type StudentForm = { name: string; email: string; mobile: string; curriculum_id: string; class_level: number };
const EMPTY_FORM: StudentForm = { name: "", email: "", mobile: "", curriculum_id: "", class_level: 8 };

function usesEmailLogin(student: ManagedStudent) {
  return student.email !== null && student.login_identifier === student.email;
}

export default function StudentsPage() {
  const [items, setItems] = useState<ManagedStudent[] | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | StudentStatus>("");
  const [form, setForm] = useState<StudentForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<ManagedStudent | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [credentials, setCredentials] = useState<StudentCredentials | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    try {
      const response = await api<StudentListResponse>(`/teacher/students?${params.toString()}`);
      setItems(response.items); setTotal(response.total);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Students could not be loaded");
    } finally { setLoading(false); }
  }, [offset, search, status]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { api<{ configured_curricula: Curriculum[] }>("/curriculum/options").then(response => setCurricula(response.configured_curricula)).catch(() => undefined); }, []);

  function submitSearch(event: FormEvent) {
    event.preventDefault(); setOffset(0); setSearch(searchInput.trim());
  }

  function openCreate() {
    const defaultCurriculum = curricula.find(item => item.board === "cbse" && item.class_level === 8) ?? curricula[0];
    setEditing(null); setForm({ ...EMPTY_FORM, curriculum_id: defaultCurriculum?.id ?? "", class_level: defaultCurriculum?.class_level ?? 8 }); setFormError(""); setFormOpen(true);
  }

  async function openEdit(student: ManagedStudent) {
    setActionId(student.id); setError("");
    try {
      const response = await api<{ student: ManagedStudent }>(`/teacher/students/${student.id}`);
      const current = response.student;
      setEditing(current);
      setForm({ name: current.name, email: current.email ?? "", mobile: current.mobile ?? "", curriculum_id: current.curriculum_id, class_level: current.class_level });
      setFormError(""); setFormOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Student details could not be loaded");
    } finally { setActionId(null); }
  }

  async function saveStudent(event: FormEvent) {
    event.preventDefault(); setFormError(""); setSuccess("");
    const name = form.name.trim(); const email = form.email.trim().toLowerCase(); const mobile = form.mobile.trim();
    if (!name) { setFormError("Student name is required."); return; }
    if (!email) { setFormError("Student email is required and will be used to sign in."); return; }
    if (!form.curriculum_id) { setFormError("Select the student's board and class curriculum."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setFormError("Enter a valid email address."); return; }
    setSaving(true);
    const body = JSON.stringify({ name, email, mobile: mobile || null, curriculum_id: form.curriculum_id, class_level: form.class_level });
    try {
      if (editing) {
        await api<{ student: ManagedStudent }>(`/teacher/students/${editing.id}`, { method: "PATCH", body });
        setSuccess(`${name} was updated.`);
      } else {
        const created = await api<StudentCredentials>("/teacher/students", { method: "POST", body });
        setCredentials(created); setSuccess(`${created.student.name} was created.`);
      }
      setFormOpen(false); setForm(EMPTY_FORM); setEditing(null); await load();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Student could not be saved");
    } finally { setSaving(false); }
  }

  async function changeStatus(student: ManagedStudent) {
    const action = student.status === "active" ? "deactivate" : "activate";
    const warning = action === "deactivate" ? `${student.name} will immediately lose access, including existing sessions. Continue?` : `${student.name} will be able to sign in again. Continue?`;
    if (!window.confirm(warning)) return;
    setActionId(student.id); setError(""); setSuccess("");
    try {
      await api<{ student: ManagedStudent }>(`/teacher/students/${student.id}/${action}`, { method: "POST" });
      setSuccess(`${student.name} was ${action}d.`); await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Student could not be ${action}d`);
    } finally { setActionId(null); }
  }

  async function resetPassword(student: ManagedStudent) {
    if (!window.confirm(`Generate a new temporary password for ${student.name}? Existing sessions will be invalidated.`)) return;
    setActionId(student.id); setError(""); setSuccess("");
    try {
      const result = await api<StudentCredentials>(`/teacher/students/${student.id}/reset-password`, { method: "POST" });
      setCredentials(result); setSuccess(`Password reset for ${student.name}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Password could not be reset");
    } finally { setActionId(null); }
  }

  async function copyCredentials() {
    if (!credentials) return;
    try {
      const loginLabel = usesEmailLogin(credentials.student) ? "Login email" : "Legacy login ID";
      await navigator.clipboard.writeText(`${loginLabel}: ${credentials.student.login_identifier}\nTemporary password: ${credentials.temporary_password}\nThe student must change this password after signing in.`);
      setSuccess("Credentials copied. Share them securely.");
    } catch { setError("Could not copy automatically. Copy the credentials manually."); }
  }

  return <>
    <div className="page-header"><div><p className="eyebrow">Teacher administration</p><h1>Students</h1><p className="muted">Manage student curriculum eligibility and access without deleting academic history.</p></div><button onClick={openCreate}>Add student</button></div>
    {error && <Notice kind="error">{error}</Notice>}{success && <Notice kind="success">{success}</Notice>}
    <section className="card student-toolbar"><form className="student-search" onSubmit={submitSearch}>
      <label>Search<input value={searchInput} onChange={event => setSearchInput(event.target.value)} placeholder="Name, email or login ID" /></label>
      <label>Status<select value={status} onChange={event => { setOffset(0); setStatus(event.target.value as "" | StudentStatus); }}><option value="">All</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
      <button type="submit">Search</button>{(search || status) && <button type="button" className="secondary" onClick={() => { setSearchInput(""); setSearch(""); setStatus(""); setOffset(0); }}>Clear</button>}
    </form></section>
    <section className="card" style={{ marginTop: "1rem" }}>
      {loading && items !== null && <p className="muted" aria-live="polite">Refreshing students...</p>}
      {loading && items === null ? <Spinner label="Loading students..." /> : !items?.length ? <Empty>No students match the current filters.</Empty> : <div className="table-wrap"><table>
        <thead><tr><th>Name</th><th>Login ID</th><th>Class</th><th>Status</th><th>Created date</th><th>Actions</th></tr></thead>
        <tbody>{items.map(student => <tr key={student.id}><td><strong>{student.name}</strong>{student.mobile && <small className="student-contact">{student.mobile}</small>}</td><td><code>{student.login_identifier}</code>{!usesEmailLogin(student) && <small className="student-contact legacy-login">Legacy login - email required when editing</small>}</td><td>{student.board === "state" ? `State (${student.state_code})` : student.board.toUpperCase()} · Class {student.class_level}</td><td><Pill>{student.status}</Pill></td><td>{new Date(student.created_at).toLocaleDateString()}</td><td><div className="actions"><button className="secondary" disabled={actionId === student.id} onClick={() => void openEdit(student)}>Edit</button><button className="secondary" disabled={actionId === student.id} onClick={() => void resetPassword(student)}>Reset password</button><button className={student.status === "active" ? "danger" : "secondary"} disabled={actionId === student.id} onClick={() => void changeStatus(student)}>{student.status === "active" ? "Deactivate" : "Activate"}</button></div></td></tr>)}</tbody>
      </table></div>}
      {items && total > 0 && <div className="student-pagination"><span>{offset + 1}-{Math.min(offset + items.length, total)} of {total}</span><div className="actions"><button className="secondary" disabled={offset === 0 || loading} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Previous</button><button className="secondary" disabled={offset + items.length >= total || loading} onClick={() => setOffset(value => value + PAGE_SIZE)}>Next</button></div></div>}
    </section>
    {formOpen && <div className="dialog-scrim"><dialog open className="student-dialog" aria-labelledby="student-form-title"><form className="stack" onSubmit={saveStudent}>
      <div><p className="eyebrow">Student record</p><h2 id="student-form-title">{editing ? "Edit student" : "Add student"}</h2></div>{formError && <Notice kind="error">{formError}</Notice>}
      <label>Name<input required maxLength={200} value={form.name} onChange={event => setForm(value => ({ ...value, name: event.target.value }))} /></label>
      <div className="grid two"><label>Email<input type="email" autoComplete="email" required maxLength={320} value={form.email} onChange={event => setForm(value => ({ ...value, email: event.target.value }))} /></label><label>Mobile (optional)<input type="tel" maxLength={30} value={form.mobile} onChange={event => setForm(value => ({ ...value, mobile: event.target.value }))} /></label></div>
      <label>Board and class<select required value={form.curriculum_id} onChange={event => { const selected = curricula.find(item => item.id === event.target.value); setForm(value => ({ ...value, curriculum_id: event.target.value, class_level: selected?.class_level ?? value.class_level })); }}><option value="">Choose curriculum</option>{curricula.map(item => <option key={item.id} value={item.id}>{item.board === "state" ? `State Board (${item.state_code})` : item.board.toUpperCase()} - Class {item.class_level}</option>)}</select></label><p className="muted">The normalized email address is the student's login. Curriculum changes affect future assignment eligibility but preserve academic history. {editing && !usesEmailLogin(editing) ? "This legacy account will be converted to email login when saved." : !editing ? "A temporary password will be shown once after creation." : "Changing the email preserves the student's academic history."}</p>
      <div className="actions"><button type="button" className="secondary" disabled={saving} onClick={() => { setFormOpen(false); setEditing(null); setFormError(""); }}>Cancel</button><button type="submit" disabled={saving}>{saving ? "Saving..." : editing ? "Save changes" : "Create student"}</button></div>
    </form></dialog></div>}
    {credentials && <div className="dialog-scrim"><dialog open className="student-dialog" aria-labelledby="credentials-title"><div className="stack">
      <div><p className="eyebrow">Shown once</p><h2 id="credentials-title">Temporary credentials</h2></div><Notice kind="success">Copy these credentials now. The temporary password cannot be displayed again, and the student must change it immediately after signing in.</Notice>
      <div className="credential-box"><span>Student</span><strong>{credentials.student.name}</strong><span>{usesEmailLogin(credentials.student) ? "Login email" : "Legacy login ID"}</span><code>{credentials.student.login_identifier}</code><span>Temporary password</span><code>{credentials.temporary_password}</code></div>
      <div className="actions"><button className="secondary" onClick={() => void copyCredentials()}>Copy credentials</button><button onClick={() => setCredentials(null)}>I have saved them</button></div>
    </div></dialog></div>}
  </>;
}
