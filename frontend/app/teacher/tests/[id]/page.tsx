"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { TestAssignmentStudent } from "@/lib/types";
import { Notice, Pill, Spinner } from "@/components/Ui";

interface TeacherTest { id: string; title: string; instructions: string; status: "draft" | "published"; total_marks: number; student_ids: string[]; assignment_students: TestAssignmentStudent[]; questions: Array<{ id: string; order: number; text: string; type: string; marks: number; board_label: string; class_level: number; subject_label: string; textbook_label: string; chapter_label: string }> }

export default function TeacherTestPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<TeacherTest | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const load = () => api<TeacherTest>(`/tests/${id}`).then(setData).catch(caught => setError(caught.message));
  useEffect(() => { void load(); }, [id]);
  async function publish() {
    if (!confirm("Publish this approved test to the selected students? Published question content cannot be changed.")) return;
    setBusy(true); setError("");
    try { await api(`/tests/${id}/publish`, { method: "POST" }); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to publish"); }
    finally { setBusy(false); }
  }
  async function assignStudents() {
    if (!selected.length) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      const response = await api<{ added_student_ids: string[] }>(`/tests/${id}/assignments`, { method: "POST", body: JSON.stringify({ student_ids: selected }) });
      setSuccess(`${response.added_student_ids.length} student${response.added_student_ids.length === 1 ? "" : "s"} assigned.`);
      setSelected([]); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Students could not be assigned"); }
    finally { setBusy(false); }
  }
  if (!data) return error ? <Notice kind="error">{error}</Notice> : <Spinner />;
  const scope = data.questions[0];
  return <><div className="page-header"><div><p className="eyebrow">Test</p><h1>{data.title}</h1><p>{data.total_marks} marks - {data.questions.length} questions - {data.student_ids.length} assigned students</p>{scope && <p className="muted">{scope.board_label} | Class {scope.class_level} | {scope.subject_label} | {scope.textbook_label}</p>}</div><Pill>{data.status}</Pill></div>
    {error && <Notice kind="error">{error}</Notice>}{success && <Notice kind="success">{success}</Notice>}{data.instructions && <section className="card"><h2>Instructions</h2><p>{data.instructions}</p></section>}
    <section className="card" style={{ marginTop: "1rem" }}><h2>Student assignments</h2><p className="muted">Assignments are additive. Existing assignments, attempts and results are never removed when new students are added.</p>
      <div className="grid two">
        <div><h3>Assigned students ({data.assignment_students.filter(student => student.assigned).length})</h3>{!data.assignment_students.some(student => student.assigned) ? <p className="muted">No students assigned.</p> : <div className="list">{data.assignment_students.filter(student => student.assigned).map(student => <div className="list-row" key={student.id}><div><strong>{student.name}</strong><small className="student-contact">{student.login_identifier}</small></div><Pill>{student.attempt_status?.replaceAll("_", " ") ?? "assigned"}</Pill></div>)}</div>}</div>
        <div><h3>Unassigned students</h3>{!data.assignment_students.some(student => !student.assigned) ? <p className="muted">No unassigned students in this curriculum.</p> : <fieldset className="stack">{data.assignment_students.filter(student => !student.assigned).map(student => <label className="option" key={student.id}><input type="checkbox" disabled={student.status !== "active" || busy} checked={selected.includes(student.id)} onChange={event => setSelected(current => event.target.checked ? [...current, student.id] : current.filter(id => id !== student.id))} /><span><strong>{student.name}</strong><small className="student-contact">{student.login_identifier}{student.status !== "active" ? " · inactive (cannot assign)" : ""}</small></span></label>)}</fieldset>}<button style={{ marginTop: ".75rem" }} disabled={!selected.length || busy} onClick={() => void assignStudents()}>{busy ? "Assigning..." : `Assign selected (${selected.length})`}</button></div>
      </div>
    </section>
    <section className="stack" style={{ marginTop: "1rem" }}>{data.questions.map(question => <article className="card" key={question.id}><div className="question-meta"><strong>Question {question.order}</strong><Pill>{question.type.replaceAll("_", " ")}</Pill><span>{question.marks} marks</span><span>{question.chapter_label}</span></div><p>{question.text}</p></article>)}</section>
    {data.status === "draft" ? <div className="sticky-actions"><span>Publication validates that every included question is approved.</span><button disabled={busy} onClick={() => void publish()}>{busy ? "Publishing..." : "Publish test"}</button></div> : <Notice kind="success">Published. Assigned students can now start this test.</Notice>}
  </>;
}
