"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Notice, Pill, Spinner } from "@/components/Ui";

interface TeacherTest { id: string; title: string; instructions: string; status: "draft" | "published"; total_marks: number; student_ids: string[]; questions: Array<{ id: string; order: number; text: string; type: string; marks: number; board_label: string; class_level: number; subject_label: string; textbook_label: string; chapter_label: string }> }

export default function TeacherTestPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<TeacherTest | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api<TeacherTest>(`/tests/${id}`).then(setData).catch(caught => setError(caught.message));
  useEffect(() => { void load(); }, [id]);
  async function publish() {
    if (!confirm("Publish this approved test to the selected students? Published question content cannot be changed.")) return;
    setBusy(true); setError("");
    try { await api(`/tests/${id}/publish`, { method: "POST" }); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to publish"); }
    finally { setBusy(false); }
  }
  if (!data) return error ? <Notice kind="error">{error}</Notice> : <Spinner />;
  const scope = data.questions[0];
  return <><div className="page-header"><div><p className="eyebrow">Test</p><h1>{data.title}</h1><p>{data.total_marks} marks - {data.questions.length} questions - {data.student_ids.length} assigned students</p>{scope && <p className="muted">{scope.board_label} | Class {scope.class_level} | {scope.subject_label} | {scope.textbook_label}</p>}</div><Pill>{data.status}</Pill></div>
    {error && <Notice kind="error">{error}</Notice>}{data.instructions && <section className="card"><h2>Instructions</h2><p>{data.instructions}</p></section>}
    <section className="stack" style={{ marginTop: "1rem" }}>{data.questions.map(question => <article className="card" key={question.id}><div className="question-meta"><strong>Question {question.order}</strong><Pill>{question.type.replaceAll("_", " ")}</Pill><span>{question.marks} marks</span><span>{question.chapter_label}</span></div><p>{question.text}</p></article>)}</section>
    {data.status === "draft" ? <div className="sticky-actions"><span>Publication validates that every included question is approved.</span><button disabled={busy} onClick={() => void publish()}>{busy ? "Publishing..." : "Publish test"}</button></div> : <Notice kind="success">Published. Assigned students can now start this test.</Notice>}
  </>;
}
