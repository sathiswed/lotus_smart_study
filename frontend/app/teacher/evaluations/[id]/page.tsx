"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { EvaluationStatus, TeacherAttempt } from "@/lib/types";
import { Notice, Pill, Spinner } from "@/components/Ui";

type AttemptQuestion = TeacherAttempt["questions"][number];
type SavedEvaluation = NonNullable<AttemptQuestion["evaluation"]>;

function statusMarks(status: EvaluationStatus, maximum: number, current: number) {
  if (status === "correct") return maximum;
  if (status === "wrong") return 0;
  return current > 0 && current < maximum ? current : Math.max(0.5, Math.min(maximum - 0.5, maximum / 2));
}

export default function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [data, setData] = useState<TeacherAttempt | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string[]>([]);
  const [dirty, setDirty] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<TeacherAttempt>(`/teacher/attempts/${id}`).then(setData).catch(caught => setError(caught.message)); }, [id]);
  const complete = useMemo(() => data?.questions.every(question => !!question.evaluation) ?? false, [data]);
  const total = useMemo(() => data?.questions.reduce((sum, question) => sum + Number(question.evaluation?.awarded_marks ?? 0), 0) ?? 0, [data]);
  const maximum = useMemo(() => data?.questions.reduce((sum, question) => sum + question.marks, 0) ?? 0, [data]);

  function updateLocal(questionId: string, patch: Partial<SavedEvaluation>) {
    if (data?.status === "result_published") return;
    setData(current => current ? { ...current, questions: current.questions.map(question => question.id === questionId ? { ...question, evaluation: { status: question.evaluation?.status ?? "wrong", awarded_marks: question.evaluation?.awarded_marks ?? 0, feedback: question.evaluation?.feedback, version: question.evaluation?.version ?? 0, ...patch } } : question) } : current);
    setDirty(current => current.includes(questionId) ? current : [...current, questionId]);
  }

  function applySaved(questionId: string, evaluation: SavedEvaluation) {
    setData(current => current ? { ...current, questions: current.questions.map(question => question.id === questionId ? { ...question, evaluation } : question) } : current);
    setDirty(current => current.filter(value => value !== questionId));
  }

  async function save(questionId: string, evaluation: SavedEvaluation) {
    if (data?.status === "result_published") return;
    setSaving(current => [...current, questionId]); setError("");
    try {
      const result = await api<SavedEvaluation>(`/teacher/attempts/${id}/evaluations/${questionId}`, { method: "PUT", body: JSON.stringify(evaluation) });
      applySaved(questionId, result);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Evaluation could not be saved";
      try { setData(await api<TeacherAttempt>(`/teacher/attempts/${id}`)); setDirty(current => current.filter(value => value !== questionId)); }
      catch { /* retain the dirty marker so publication remains blocked */ }
      setError(`${message}. The displayed marks were restored from the server where possible.`);
    }
    finally { setSaving(current => current.filter(value => value !== questionId)); }
  }

  function setStatus(question: AttemptQuestion, status: EvaluationStatus) {
    if (data?.status === "result_published") return;
    const evaluation = { status, awarded_marks: statusMarks(status, question.marks, Number(question.evaluation?.awarded_marks ?? 0)), feedback: question.evaluation?.feedback ?? "", version: question.evaluation?.version ?? 0 };
    updateLocal(question.id, evaluation);
    void save(question.id, evaluation);
  }

  async function publish() {
    if (!complete || !data || dirty.length || saving.length) return;
    if (!confirm(`Publish ${total}/${maximum} to ${data.student.name}? Published results cannot be reopened.`)) return;
    setBusy(true); setError("");
    try { await api(`/teacher/attempts/${id}/results/publish`, { method: "POST" }); router.push("/teacher/evaluations"); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not publish result"); }
    finally { setBusy(false); }
  }

  if (!data) return error ? <Notice kind="error">{error}</Notice> : <Spinner />;
  const locked = data.status === "result_published";
  return <><div className="page-header"><div><p className="eyebrow">Student answer sheet</p><h1>{data.test.title}</h1><p>{data.student.name} - <span className="marks">{total}/{maximum}</span></p></div><Pill>{data.status.replaceAll("_", " ")}</Pill></div>
    {error && <Notice kind="error">{error}</Notice>}
    {locked && <Notice kind="success">This published result is a permanent read-only record. Marks and feedback can no longer be changed.</Notice>}
    <section className="stack">{data.questions.map(question => <article className="card question-card" key={question.id}>
      <div className="question-meta"><strong>Question {question.order}</strong><Pill>{question.type.replaceAll("_", " ")}</Pill><span>{question.marks} marks</span><span className="save-state">{saving.includes(question.id) ? "Saving..." : dirty.includes(question.id) ? "Unsaved" : question.evaluation ? "Saved" : "Unmarked"}</span></div>
      <p style={{ whiteSpace: "pre-wrap" }}>{question.text}</p>
      <div className="card"><strong>Student answer</strong>{question.type === "mcq" ? <p>Selected: {question.options?.find(option => option.id === question.answer?.selected_option_id)?.text ?? "Unanswered"}</p> : <p style={{ whiteSpace: "pre-wrap" }}>{question.answer?.text_answer || "Unanswered"}</p>}
        {!!question.answer?.images?.length && <div className="image-grid">{question.answer.images.map((image, index) => <a className="image-card" href={image.preview_url} target="_blank" rel="noreferrer" key={image.id}><img src={image.preview_url} alt={`Submitted page ${index + 1}`} /><span>Open page {index + 1} to zoom</span></a>)}</div>}
      </div>
      <div className="card" style={{ marginTop: ".75rem" }}><strong>Teacher reference answer</strong><p style={{ whiteSpace: "pre-wrap" }}>{question.reference_answer}</p></div>
      <div className="stack" style={{ marginTop: ".75rem" }}><fieldset><legend>Evaluation status</legend><div className="actions">{(["correct", "partial", "wrong"] as EvaluationStatus[]).map(status => <button disabled={locked || saving.includes(question.id)} className={question.evaluation?.status === status ? "" : "secondary"} key={status} onClick={() => setStatus(question, status)}>{status[0].toUpperCase() + status.slice(1)}</button>)}</div></fieldset>
        <label>Awarded marks<input type="number" min="0" max={question.marks} step="0.5" disabled={locked || question.evaluation?.status !== "partial" || saving.includes(question.id)} value={question.evaluation?.awarded_marks ?? 0} onChange={event => updateLocal(question.id, { awarded_marks: Number(event.target.value) })} onBlur={() => { const current = data.questions.find(item => item.id === question.id)?.evaluation; if (current) void save(question.id, current); }} /></label>
        <label>Feedback (optional)<textarea disabled={locked || saving.includes(question.id)} value={question.evaluation?.feedback ?? ""} onChange={event => updateLocal(question.id, { feedback: event.target.value })} onBlur={() => { const current = data.questions.find(item => item.id === question.id)?.evaluation; if (current) void save(question.id, current); }} /></label>
      </div>
    </article>)}</section>
    {!locked && <div className="sticky-actions"><span><strong>{total}/{maximum}</strong> - {dirty.length ? "Save all changes before publishing" : complete ? "All questions marked" : "Mark every question before publishing"}</span><button disabled={!complete || busy || !!saving.length || !!dirty.length} onClick={() => void publish()}>{busy ? "Publishing..." : "Publish result"}</button></div>}
  </>;
}
