"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { AnswerImage, Attempt, StudentAnswer, StudentQuestion } from "@/lib/types";
import { Notice, Pill, Spinner } from "@/components/Ui";

const DEBOUNCE = Number(process.env.NEXT_PUBLIC_TEXT_AUTOSAVE_MS ?? 750);
const answerFor = (attempt: Attempt | null, questionId: string) => attempt?.answers.find(answer => answer.test_question_id === questionId);
const draftKey = (attemptId: string, questionId: string) => `lotus:answer-draft:${attemptId}:${questionId}`;
type SupportedImageType = "image/jpeg" | "image/png" | "image/webp";

async function detectImageType(file: File): Promise<SupportedImageType> {
  const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return "image/jpeg";
  if (bytes.length >= 8 && [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((value, index) => bytes[index] === value)) return "image/png";
  if (bytes.length >= 12 && String.fromCharCode(...bytes.slice(0, 4)) === "RIFF" && String.fromCharCode(...bytes.slice(8, 12)) === "WEBP") return "image/webp";
  throw new Error(`${file.name}: the file content is not a supported JPEG, PNG, or WebP image.`);
}

function uploadFile(url: string, method: "PUT", headers: Record<string, string>, file: File, onProgress: (percentage: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(method, url);
    for (const [name, value] of Object.entries(headers)) request.setRequestHeader(name, value);
    request.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100)); };
    request.onload = () => request.status >= 200 && request.status < 300 ? resolve() : reject(new Error(`${file.name}: storage upload failed.`));
    request.onerror = () => reject(new Error(`${file.name}: storage upload failed.`));
    request.send(file);
  });
}

export default function AttemptPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [index, setIndex] = useState(0);
  const [localText, setLocalText] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [showSubmit, setShowSubmit] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveChain = useRef<Promise<void>>(Promise.resolve());
  const versions = useRef<Record<string, number>>({});
  const inputRef = useRef<HTMLInputElement | null>(null);
  const question = attempt?.questions[index];
  const stored = question ? answerFor(attempt, question.id) : undefined;
  const shortAnswerMaxChars = attempt?.short_answer_max_chars ?? 4000;

  const load = () => api<Attempt>(`/student/attempts/${id}`).then(value => {
    for (const answer of value.answers) versions.current[answer.test_question_id] = answer.version;
    setAttempt(value);
  }).catch(caught => setError(caught.message));
  useEffect(() => { void load(); return () => { if (timer.current) clearTimeout(timer.current); }; }, [id]);
  useEffect(() => {
    if (!question || question.type === "mcq" || attempt?.status !== "in_progress") { setLocalText(""); setSaveState("idle"); return; }
    let pending: string | null = null;
    try { pending = localStorage.getItem(draftKey(id, question.id)); } catch { /* storage can be unavailable */ }
    setLocalText(pending ?? stored?.text_answer ?? "");
    setSaveState(pending === null ? "idle" : "saving");
    if (pending !== null) {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => { void save(question, { text_answer: pending! }).catch(() => undefined); }, 0);
    }
  }, [question?.id, stored?.id, attempt?.status]);
  useEffect(() => {
    if (saveState !== "saving" && saveState !== "error") return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [saveState]);
  useEffect(() => {
    if (!attempt || attempt.status === "in_progress") return;
    try { for (const item of attempt.questions) localStorage.removeItem(draftKey(id, item.id)); }
    catch { /* storage can be unavailable */ }
  }, [attempt?.status, id]);

  const unanswered = useMemo(() => attempt?.questions.filter(item => {
    const answer = answerFor(attempt, item.id);
    return !(answer?.selected_option_id || answer?.text_answer?.trim() || (answer?.images?.length ?? 0) > 0);
  }).length ?? 0, [attempt]);

  function mergeAnswer(next: StudentAnswer) {
    versions.current[next.test_question_id] = next.version;
    setAttempt(current => {
      if (!current) return current;
      const previous = current.answers.find(answer => answer.test_question_id === next.test_question_id);
      const merged = { ...next, images: next.images ?? previous?.images };
      return { ...current, answers: [...current.answers.filter(answer => answer.test_question_id !== next.test_question_id), merged] };
    });
  }

  async function save(item: StudentQuestion, payload: { selected_option_id?: string; text_answer?: string }) {
    const operation = saveChain.current.then(async () => {
      setSaveState("saving"); setError("");
      const next = await api<StudentAnswer>(`/student/attempts/${id}/answers/${item.id}`, { method: "PUT", body: JSON.stringify({ answer_type: item.type === "mcq" ? "mcq" : "text", ...payload, version: versions.current[item.id] ?? 0 }) });
      mergeAnswer(next);
      if (payload.text_answer !== undefined) {
        try {
          const key = draftKey(id, item.id);
          if (localStorage.getItem(key) === payload.text_answer) localStorage.removeItem(key);
          setSaveState(localStorage.getItem(key) === null ? "saved" : "saving");
        } catch { setSaveState("saved"); }
      } else setSaveState("saved");
      return next;
    });
    saveChain.current = operation.then(() => undefined, () => undefined);
    try { return await operation; }
    catch (caught) { setSaveState("error"); setError(caught instanceof Error ? caught.message : "Answer could not be saved"); throw caught; }
  }

  function textChanged(value: string) {
    setLocalText(value); setSaveState("saving");
    if (question) { try { localStorage.setItem(draftKey(id, question.id), value); } catch { /* autosave still uses the API */ } }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { if (question) void save(question, { text_answer: value }).catch(() => undefined); }, DEBOUNCE);
  }

  async function flush() {
    if (!question || question.type === "mcq") return;
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    if (localText !== (answerFor(attempt, question.id)?.text_answer ?? "")) await save(question, { text_answer: localText });
  }

  async function move(next: number) { try { await flush(); setIndex(next); } catch { /* keep the student on the unsaved question */ } }
  async function ensureAnswer() {
    if (!question || question.type === "mcq") throw new Error("Notebook photos are available only for written-answer questions.");
    return answerFor(attempt, question.id) ?? await save(question, { text_answer: localText });
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true); setError("");
    try {
      const answer = await ensureAnswer();
      for (const file of Array.from(files)) {
        const contentType = await detectImageType(file);
        const grant = await api<{ image_id: string; upload_url: string; upload_method: "PUT"; required_headers: Record<string, string> }>(`/student/answers/${answer.id}/images/upload-url`, { method: "POST", body: JSON.stringify({ file_name: file.name, content_type: contentType, byte_size: file.size }) });
        try {
          await uploadFile(grant.upload_url, grant.upload_method, grant.required_headers, file, setUploadProgress);
          await api(`/student/answers/${answer.id}/images/${grant.image_id}/complete`, { method: "POST" });
        } catch (caught) {
          await api(`/student/answers/${answer.id}/images/${grant.image_id}`, { method: "DELETE" }).catch(() => undefined);
          throw caught;
        }
      }
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Upload failed"); }
    finally { setUploading(false); setUploadProgress(null); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function removeImage(answerId: string, imageId: string) {
    if (!confirm("Remove this page?")) return;
    try { await api(`/student/answers/${answerId}/images/${imageId}`, { method: "DELETE" }); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not remove image"); }
  }

  async function reorder(answerId: string, images: AnswerImage[], from: number, to: number) {
    if (to < 0 || to >= images.length) return;
    const imageIds = images.map(image => image.id); [imageIds[from], imageIds[to]] = [imageIds[to], imageIds[from]];
    try { await api(`/student/answers/${answerId}/images/order`, { method: "PUT", body: JSON.stringify({ image_ids: imageIds }) }); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not reorder pages"); }
  }

  async function submit() {
    setBusy(true); setError("");
    try { await flush(); await api(`/student/attempts/${id}/submit`, { method: "POST" }); setShowSubmit(false); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not submit test"); }
    finally { setBusy(false); }
  }

  if (!attempt) return error ? <Notice kind="error">{error}</Notice> : <Spinner />;
  if (attempt.status !== "in_progress") return <><div className="page-header"><div><p className="eyebrow">Submission complete</p><h1>{attempt.test_title ?? "Test submitted"}</h1></div><Pill>{attempt.status.replaceAll("_", " ")}</Pill></div><Notice kind="success">Your answers are locked and waiting for teacher evaluation.</Notice><button onClick={() => router.push("/student")}>Return to dashboard</button></>;
  if (!question) return <Notice kind="error">This attempt has no questions.</Notice>;
  const images = stored?.images ?? [];

  return <><div className="page-header"><div><p className="eyebrow">Active test</p><h1>{attempt.test_title ?? "Assigned test"}</h1><p>{unanswered} unanswered</p></div><span className={`save-state ${saveState === "error" ? "error" : ""}`}>{uploading ? `Uploading photo${uploadProgress === null ? "..." : ` ${uploadProgress}%`}` : saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : ""}</span></div>
    {error && <Notice kind="error">{error}</Notice>}
    <nav className="question-nav" aria-label="Question navigation">{attempt.questions.map((item, itemIndex) => <button className={itemIndex === index ? "current" : "secondary"} key={item.id} onClick={() => void move(itemIndex)} aria-label={`Question ${itemIndex + 1}`}>{itemIndex + 1}</button>)}</nav>
    <article className="card question-card"><div className="question-meta"><strong>Question {question.order ?? index + 1}</strong><Pill>{question.type.replaceAll("_", " ")}</Pill><span>{question.marks} marks</span></div><p style={{ whiteSpace: "pre-wrap" }}>{question.text}</p>
      {question.type === "mcq" ? <div className="options">{question.options?.map(option => <label className="option" key={option.id}><input type="radio" name={question.id} disabled={saveState === "saving"} checked={stored?.selected_option_id === option.id} onChange={() => void save(question, { selected_option_id: option.id }).catch(() => undefined)} /><span>{option.text}</span></label>)}</div> : <label>Your answer<textarea maxLength={shortAnswerMaxChars} value={localText} onChange={event => textChanged(event.target.value)} onBlur={() => void flush().catch(() => undefined)} placeholder="Type a short answer, or add notebook photos below." /><small>{localText.length}/{shortAnswerMaxChars}</small></label>}
      {question.type !== "mcq" && <section style={{ marginTop: "1rem" }}><h2>Notebook photos</h2><p className="muted">Add JPEG, PNG, or WebP pages in reading order. You can remove or reorder them before submission.</p><input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple onChange={(event: ChangeEvent<HTMLInputElement>) => void upload(event.target.files)} disabled={uploading} />
        {!!images.length && <div className="image-grid" style={{ marginTop: "1rem" }}>{images.map((image, imageIndex) => <div className="card image-card" key={image.id}><img src={image.preview_url} alt={`Notebook page ${imageIndex + 1}`} /><p>Page {imageIndex + 1}</p><div className="actions"><button className="secondary" onClick={() => void reorder(stored!.id, images, imageIndex, imageIndex - 1)} disabled={imageIndex === 0}>Up</button><button className="secondary" onClick={() => void reorder(stored!.id, images, imageIndex, imageIndex + 1)} disabled={imageIndex === images.length - 1}>Down</button><button className="danger" onClick={() => void removeImage(stored!.id, image.id)}>Remove</button></div></div>)}</div>}
      </section>}
    </article>
    <div className="sticky-actions"><button className="secondary" disabled={index === 0 || saveState === "saving" || uploading} onClick={() => void move(index - 1)}>Previous</button>{index < attempt.questions.length - 1 ? <button disabled={saveState === "saving" || uploading} onClick={() => void move(index + 1)}>Next</button> : <button disabled={saveState === "saving" || uploading} onClick={() => setShowSubmit(true)}>Review & submit</button>}</div>
    {showSubmit && <dialog open><h2>Submit test?</h2><p>{unanswered} question{unanswered === 1 ? " is" : "s are"} unanswered. Submission locks all answers and photos.</p><div className="actions"><button className="secondary" onClick={() => setShowSubmit(false)}>Keep working</button><button disabled={busy || uploading || saveState === "saving"} onClick={() => void submit()}>{busy ? "Submitting..." : "Submit test"}</button></div></dialog>}
  </>;
}
