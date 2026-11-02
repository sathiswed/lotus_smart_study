"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { GenerationBatch, Student, TeacherQuestion } from "@/lib/types";
import { Notice, Pill, Spinner } from "@/components/Ui";

function QuestionEditor({ question, onChanged }: { question: TeacherQuestion; onChanged: (question: TeacherQuestion, oldId: string) => void }) {
  const [draft, setDraft] = useState(question);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  useEffect(() => setDraft(question), [question]);

  const editablePayload = (value: TeacherQuestion) => ({
    text: value.text,
    marks: value.marks,
    options: value.options,
    correct_option_id: value.correct_option_id,
    reference_answer: value.reference_answer,
  });
  const dirty = JSON.stringify(editablePayload(draft)) !== JSON.stringify(editablePayload(question));

  async function action(name: "save" | "approve" | "reject" | "regenerate") {
    setBusy(name);
    setError("");
    try {
      let next: TeacherQuestion;
      if (name === "save") {
        next = await api<TeacherQuestion>(`/questions/${question.id}`, { method: "PATCH", body: JSON.stringify(editablePayload(draft)) });
      } else if (name === "approve" && dirty) {
        const saved = await api<TeacherQuestion>(`/questions/${question.id}`, { method: "PATCH", body: JSON.stringify(editablePayload(draft)) });
        next = await api<TeacherQuestion>(`/questions/${saved.id}/approve`, { method: "POST" });
      } else {
        next = await api<TeacherQuestion>(`/questions/${question.id}/${name}`, { method: "POST" });
      }
      onChanged(next, question.id);
      setDraft(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Action failed");
    } finally { setBusy(""); }
  }

  function optionChange(index: number, value: string) {
    setDraft(current => ({ ...current, options: (current.options ?? []).map((option, optionIndex) => optionIndex === index ? { ...option, text: value } : option) }));
  }

  return <article className="card question-card">
    <div className="question-meta"><Pill>{question.status}</Pill><Pill>{question.type.replaceAll("_", " ")}</Pill><span>{draft.marks} marks</span>{dirty && <span className="save-state">Unsaved edits</span>}</div>
    {error && <Notice kind="error">{error}</Notice>}
    <div className="stack">
      <label>Question<textarea disabled={question.status !== "draft"} value={draft.text} onChange={event => setDraft(current => ({ ...current, text: event.target.value }))} /></label>
      <label>Marks<input disabled={question.status !== "draft"} type="number" min="1" value={draft.marks} onChange={event => setDraft(current => ({ ...current, marks: Number(event.target.value) }))} /></label>
      {draft.type === "mcq" && <fieldset><legend>Options and intended answer</legend><div className="stack">{(draft.options ?? []).map((option, index) => <div className="option" key={option.id}>
        <input disabled={question.status !== "draft"} type="radio" name={`correct-${question.id}`} checked={draft.correct_option_id === option.id} onChange={() => setDraft(current => ({ ...current, correct_option_id: option.id }))} />
        <input disabled={question.status !== "draft"} aria-label={`Option ${index + 1}`} value={option.text} onChange={event => optionChange(index, event.target.value)} />
      </div>)}</div></fieldset>}
      <label>Teacher reference answer<textarea disabled={question.status !== "draft"} value={draft.reference_answer} onChange={event => setDraft(current => ({ ...current, reference_answer: event.target.value }))} /></label>
      {!!draft.validation_flags?.length && <Notice>Review flags: {draft.validation_flags.join(", ")}</Notice>}
      <div className="actions">
        <button onClick={() => void action("save")} disabled={!!busy || question.status !== "draft"}>{busy === "save" ? "Saving..." : "Save edits"}</button>
        <button onClick={() => void action("approve")} disabled={!!busy || question.status === "approved"} className="secondary">Approve</button>
        <button onClick={() => void action("regenerate")} disabled={!!busy || question.status === "approved"} className="secondary">Regenerate one</button>
        <button onClick={() => void action("reject")} disabled={!!busy || question.status === "rejected"} className="danger">Reject</button>
      </div>
    </div>
  </article>;
}

export default function BatchReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [batch, setBatch] = useState<GenerationBatch | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [generationBusy, setGenerationBusy] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const generationRequested = useRef(false);

  const loadBatch = () => api<GenerationBatch>(`/generation-batches/${id}`).then(setBatch);

  useEffect(() => {
    loadBatch().catch(caught => setError(caught.message));
  }, [id]);
  useEffect(() => {
    if (!batch?.curriculum_id) return;
    api<{ items: Student[] }>(`/students?curriculum_id=${batch.curriculum_id}`).then(response => setStudents(response.items)).catch(caught => setError(caught.message));
  }, [batch?.curriculum_id]);

  async function generate() {
    if (generationBusy) return;
    generationRequested.current = true;
    setGenerationBusy(true); setGenerationError(""); setError("");
    try { setBatch(await api<GenerationBatch>(`/generation-batches/${id}/generate`, { method: "POST" })); }
    catch (caught) {
      setGenerationError(caught instanceof Error ? caught.message : "Question generation failed");
      await loadBatch().catch(() => undefined);
    } finally { setGenerationBusy(false); }
  }

  useEffect(() => {
    if (batch?.status === "queued" && !generationRequested.current) void generate();
  }, [batch?.status]);

  useEffect(() => {
    if (batch?.status !== "generating") return;
    const poll = window.setInterval(() => { void loadBatch().catch(caught => setError(caught.message)); }, 2000);
    return () => window.clearInterval(poll);
  }, [batch?.status, id]);

  const approved = useMemo(() => batch?.questions.filter(question => question.status === "approved") ?? [], [batch]);
  const currentMarks = useMemo(() => batch?.questions.filter(question => question.status !== "rejected").reduce((sum, question) => sum + question.marks, 0) ?? 0, [batch]);
  function change(question: TeacherQuestion, oldId: string) { setBatch(current => current ? { ...current, questions: current.questions.map(item => item.id === oldId ? question : item) } : current); }

  async function createTest() {
    if (!batch || approved.length !== batch.questions.length || !selected.length || !title.trim()) { setError("Approve every current question, enter a title, and assign at least one student."); return; }
    setBusy(true); setError("");
    try {
      const test = await api<{ id: string }>("/tests", { method: "POST", body: JSON.stringify({ generation_batch_id: batch.id, title, instructions, question_ids: approved.map(question => question.id), student_ids: selected }) });
      router.push(`/teacher/tests/${test.id}`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to create test"); }
    finally { setBusy(false); }
  }

  if (!batch) return error ? <Notice kind="error">{error}</Notice> : <Spinner label="Loading generated questions..." />;
  return <>
    <div className="page-header"><div><p className="eyebrow">Review and approve</p><h1>Generated questions</h1><p>{approved.length} of {batch.questions.length} approved - {currentMarks} current marks</p>{batch.board && <p className="muted">{batch.board === "state" ? `State Board (${batch.state_code})` : batch.board.toUpperCase()} | Class {batch.class_level} | {batch.subject_title} | {batch.textbook_title} | {batch.chapter_title}</p>}</div><Pill>{batch.status}</Pill></div>
    {(batch.status === "queued" || batch.status === "generating") && <Notice>Generation is in progress. This page will update automatically. {batch.status === "queued" && generationError && <button disabled={generationBusy} onClick={() => void generate()}>Retry generation</button>}</Notice>}
    {batch.status === "failed" && <Notice kind="error">{batch.failure_reason ?? "Generation failed."} <button disabled={generationBusy} onClick={() => { generationRequested.current = false; void generate(); }}>{generationBusy ? "Retrying..." : "Retry generation"}</button></Notice>}
    {generationError && <Notice kind="error">{generationError}</Notice>}
    {error && <Notice kind="error">{error}</Notice>}
    <section className="stack">{batch.questions.map(question => <QuestionEditor key={question.id} question={question} onChanged={change} />)}</section>
    <section className="card" style={{ marginTop: "1rem" }}><h2>Create and assign test</h2><div className="stack">
      <label>Test title<input value={title} onChange={event => setTitle(event.target.value)} /></label><label>Instructions<textarea value={instructions} onChange={event => setInstructions(event.target.value)} /></label>
      <fieldset><legend>Eligible student assignment</legend>{students.length ? <div className="grid two">{students.map(student => <label className="option" key={student.id}><input type="checkbox" checked={selected.includes(student.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, student.id] : ids.filter(value => value !== student.id))} /><span>{student.name} <small>({student.login_identifier})</small></span></label>)}</div> : <Notice>No active students match this test's board and class curriculum.</Notice>}</fieldset>
      <button onClick={() => void createTest()} disabled={busy || batch.status !== "completed" || !batch.questions.length || approved.length !== batch.questions.length}>{busy ? "Creating..." : "Create draft test"}</button>
    </div></section>
  </>;
}
