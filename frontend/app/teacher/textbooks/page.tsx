"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BoardCode, BoardOption, ManagedTextbook } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

type UploadGrant = { textbook: ManagedTextbook; upload_url: string; upload_method: "PUT"; required_headers: Record<string, string> };

export default function TextbooksPage() {
  const [items, setItems] = useState<ManagedTextbook[] | null>(null);
  const [boards, setBoards] = useState<BoardOption[]>([]);
  const [classes, setClasses] = useState<number[]>([]);
  const [board, setBoard] = useState<BoardCode>("cbse");
  const [classLevel, setClassLevel] = useState(8);
  const [stateCode, setStateCode] = useState("");
  const [subjectCode, setSubjectCode] = useState("");
  const [subjectTitle, setSubjectTitle] = useState("");
  const [title, setTitle] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const [edition, setEdition] = useState("current");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try { setItems((await api<{ items: ManagedTextbook[] }>("/teacher/textbooks")).items); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Textbooks could not be loaded"); }
  }, []);
  useEffect(() => { void load(); api<{ boards: BoardOption[]; classes: number[] }>("/curriculum/options").then(data => { setBoards(data.boards); setClasses(data.classes); }).catch(caught => setError(caught.message)); }, [load]);

  async function upload(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    if (!file) { setError("Choose a PDF textbook."); return; }
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) { setError("Only PDF textbooks are supported."); return; }
    setBusy(true);
    try {
      const grant = await api<UploadGrant>("/teacher/textbooks/upload-url", { method: "POST", body: JSON.stringify({ board, state_code: board === "state" ? stateCode : null, class_level: classLevel, subject_code: subjectCode, subject_title: subjectTitle, title, academic_year: academicYear || null, edition, file_name: file.name, content_type: "application/pdf", byte_size: file.size }) });
      const response = await fetch(grant.upload_url, { method: grant.upload_method, headers: grant.required_headers, body: file });
      if (!response.ok) throw new Error(`Private textbook upload failed (${response.status})`);
      const completed = await api<{ message: string }>(`/teacher/textbooks/${grant.textbook.id}/complete`, { method: "POST" });
      setSuccess(completed.message);
      setTitle(""); setAcademicYear(""); setEdition("current"); setFile(null);
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Textbook upload failed"); }
    finally { setBusy(false); }
  }

  return <>
    <div className="page-header"><div><p className="eyebrow">Curriculum sources</p><h1>Textbooks</h1><p className="muted">Upload private source PDFs and track extraction/indexing readiness. Content is unavailable to generation until processing reaches Ready.</p></div></div>
    {error && <Notice kind="error">{error}</Notice>}{success && <Notice kind="success">{success}</Notice>}
    <section className="card"><h2>Upload textbook PDF</h2><form className="stack" onSubmit={upload}><div className="grid three">
      <label>Board<select value={board} onChange={event => setBoard(event.target.value as BoardCode)}>{boards.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label>
      {board === "state" && <label>State / curriculum identifier<input required value={stateCode} onChange={event => setStateCode(event.target.value)} placeholder="e.g. tamil-nadu" /></label>}
      <label>Class<select value={classLevel} onChange={event => setClassLevel(Number(event.target.value))}>{classes.map(item => <option key={item} value={item}>Class {item}</option>)}</select></label>
      <label>Subject identifier<input required maxLength={80} value={subjectCode} onChange={event => setSubjectCode(event.target.value)} placeholder="e.g. mathematics" /></label>
      <label>Subject name<input required maxLength={160} value={subjectTitle} onChange={event => setSubjectTitle(event.target.value)} placeholder="e.g. Mathematics" /></label>
      <label>Textbook title<input required maxLength={255} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>Academic year (optional)<input maxLength={40} value={academicYear} onChange={event => setAcademicYear(event.target.value)} placeholder="e.g. 2026-27" /></label>
      <label>Edition<input required maxLength={80} value={edition} onChange={event => setEdition(event.target.value)} /></label>
      <label>Private PDF<input required type="file" accept="application/pdf,.pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
    </div><Notice>Uploads are verified as PDFs, then wait for approved chapter extraction and indexing. The system does not invent chapters from an unprocessed book.</Notice><button disabled={busy}>{busy ? "Uploading..." : "Upload textbook"}</button></form></section>
    <section className="card" style={{ marginTop: "1rem" }}><h2>Textbook availability</h2>{items === null ? <Spinner /> : items.length === 0 ? <Empty>No textbooks have been uploaded.</Empty> : <div className="table-wrap"><table><thead><tr><th>Board / Class</th><th>Subject</th><th>Textbook</th><th>Edition</th><th>Status</th><th>Indexed content</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.board === "state" ? `State Board (${item.state_code})` : item.board.toUpperCase()} · Class {item.class_level}</td><td>{item.subject_title}</td><td><strong>{item.title}</strong>{item.academic_year && <small className="student-contact">{item.academic_year}</small>}</td><td>{item.edition}</td><td><Pill>{item.processing_status}</Pill>{item.failure_reason && <small className="student-contact legacy-login">{item.failure_reason}</small>}</td><td>{item.content_available ? `${item.indexed_chunk_count} chunks` : "Not available for generation"}</td></tr>)}</tbody></table></div>}</section>
  </>;
}
