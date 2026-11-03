"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  BoardCode, BoardOption, DetectedTextbookChapter, ManagedTextbook,
  Subject, Term, Textbook, TextbookFile,
} from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

type UploadGrant = {
  file: TextbookFile;
  upload_url: string;
  upload_method: "PUT";
  required_headers: Record<string, string>;
};
type LocalUpload = { name: string; status: string; error?: string };
const fileSize = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;

export default function TextbooksPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const pendingTextbookId = useRef("");
  const [boards, setBoards] = useState<BoardOption[]>([]);
  const [classes, setClasses] = useState<number[]>([]);
  const [board, setBoard] = useState<BoardCode>("cbse");
  const [classLevel, setClassLevel] = useState(8);
  const [stateCode, setStateCode] = useState("");
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [textbooks, setTextbooks] = useState<Textbook[]>([]);
  const [textbookId, setTextbookId] = useState("");
  const [terms, setTerms] = useState<Term[]>([]);
  const [termId, setTermId] = useState("");
  const [files, setFiles] = useState<TextbookFile[] | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [localUploads, setLocalUploads] = useState<LocalUpload[]>([]);
  const [reviews, setReviews] = useState<Record<string, DetectedTextbookChapter[]>>({});
  const [busyIds, setBusyIds] = useState<Record<string, boolean>>({});
  const [fileErrors, setFileErrors] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [newSubjectCode, setNewSubjectCode] = useState("");
  const [newSubjectTitle, setNewSubjectTitle] = useState("");
  const [newTextbookTitle, setNewTextbookTitle] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const [edition, setEdition] = useState("current");
  const [newTermCode, setNewTermCode] = useState("");
  const [newTermTitle, setNewTermTitle] = useState("");

  const selectedTextbook = useMemo(
    () => textbooks.find(item => item.id === textbookId) ?? null,
    [textbooks, textbookId],
  );

  useEffect(() => {
    api<{ boards: BoardOption[]; classes: number[] }>("/curriculum/options")
      .then(data => { setBoards(data.boards); setClasses(data.classes); })
      .catch(caught => setError(caught instanceof Error ? caught.message : "Curriculum options could not be loaded"));
  }, []);

  useEffect(() => {
    setSubjects([]); setSubjectId(""); setTextbooks([]); setTextbookId(""); setTerms([]); setTermId(""); setFiles(null);
    if (board === "state" && !stateCode.trim()) return;
    const params = new URLSearchParams({ board, class_level: String(classLevel) });
    if (board === "state") params.set("state_code", stateCode.trim());
    api<{ items: Subject[] }>(`/curriculum/subjects?${params}`)
      .then(data => setSubjects(data.items))
      .catch(caught => setError(caught instanceof Error ? caught.message : "Subjects could not be loaded"));
  }, [board, classLevel, stateCode]);

  useEffect(() => {
    setTextbooks([]); setTextbookId(""); setTerms([]); setTermId(""); setFiles(null);
    if (!subjectId) return;
    Promise.all([
      api<{ items: Textbook[] }>(`/curriculum/subjects/${subjectId}/textbooks`),
      api<{ items: Term[] }>(`/curriculum/terms?subject_id=${subjectId}`),
    ]).then(([bookData, termData]) => {
      setTextbooks(bookData.items);
      setTerms(termData.items);
      if (pendingTextbookId.current && bookData.items.some(item => item.id === pendingTextbookId.current)) {
        setTextbookId(pendingTextbookId.current);
        pendingTextbookId.current = "";
      }
    }).catch(caught => setError(caught instanceof Error ? caught.message : "Textbook choices could not be loaded"));
  }, [subjectId]);

  const loadFiles = useCallback(async () => {
    if (!textbookId || !termId) { setFiles(null); return; }
    try {
      const data = await api<{ items: TextbookFile[] }>(`/teacher/textbooks/${textbookId}/files?term_id=${termId}`);
      setFiles(data.items);
      setReviews(current => {
        const next = { ...current };
        for (const item of data.items) {
          if (!next[item.id]) next[item.id] = (item.approved_chapters.length ? item.approved_chapters : item.detected_chapters).map(chapter => ({ ...chapter }));
        }
        return next;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Uploaded files could not be loaded");
    }
  }, [textbookId, termId]);

  useEffect(() => { void loadFiles(); }, [loadFiles]);

  function chooseFiles(list: FileList | null) {
    setError("");
    const chosen = Array.from(list ?? []);
    const invalid = chosen.find(file => file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf"));
    if (invalid) { setSelectedFiles([]); setError(`${invalid.name} is not a PDF.`); return; }
    setSelectedFiles(chosen);
    setLocalUploads(chosen.map(file => ({ name: file.name, status: "queued" })));
  }

  function updateLocal(name: string, status: string, uploadError?: string) {
    setLocalUploads(current => current.map(item => item.name === name ? { name, status, error: uploadError } : item));
  }

  async function uploadOne(file: File) {
    let createdId = "";
    try {
      updateLocal(file.name, "requesting upload");
      const grant = await api<UploadGrant>(`/teacher/textbooks/${textbookId}/files/upload-url`, {
        method: "POST",
        body: JSON.stringify({ term_id: termId, file_name: file.name, content_type: "application/pdf", byte_size: file.size }),
      });
      createdId = grant.file.id;
      updateLocal(file.name, "uploading");
      const uploaded = await fetch(grant.upload_url, { method: grant.upload_method, headers: grant.required_headers, body: file });
      if (!uploaded.ok) {
        await api<void>(`/teacher/textbooks/${textbookId}/files/${createdId}`, { method: "DELETE" }).catch(() => undefined);
        throw new Error(`Private upload failed (${uploaded.status})`);
      }
      updateLocal(file.name, "detecting chapters");
      await api(`/teacher/textbooks/${textbookId}/files/${createdId}/complete`, { method: "POST" });
      updateLocal(file.name, "review required");
      return true;
    } catch (caught) {
      updateLocal(file.name, "failed", caught instanceof Error ? caught.message : "Upload failed");
      return false;
    }
  }

  async function uploadAll(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    if (!textbookId || !termId) { setError("Select a textbook and term before uploading."); return; }
    if (!selectedFiles.length) { setError("Choose one or more PDF files."); return; }
    setUploading(true);
    const failed: File[] = [];
    for (const file of selectedFiles) if (!await uploadOne(file)) failed.push(file);
    setUploading(false);
    setSelectedFiles(failed);
    if (!failed.length && inputRef.current) inputRef.current.value = "";
    await loadFiles();
  }

  function setReviewChapter(fileId: string, index: number, field: keyof DetectedTextbookChapter, value: string) {
    setReviews(current => ({
      ...current,
      [fileId]: (current[fileId] ?? []).map((chapter, chapterIndex) => chapterIndex === index
        ? { ...chapter, [field]: field === "page_start" || field === "page_end" ? Number(value) : value }
        : chapter),
    }));
  }

  function addChapter(item: TextbookFile) {
    setReviews(current => ({
      ...current,
      [item.id]: [...(current[item.id] ?? []), { code: "", title: "", page_start: 1, page_end: item.page_count ?? 1, confidence: "low" }],
    }));
  }

  function removeChapter(fileId: string, index: number) {
    setReviews(current => ({ ...current, [fileId]: (current[fileId] ?? []).filter((_, itemIndex) => itemIndex !== index) }));
  }

  async function fileAction(item: TextbookFile, action: "detect" | "finalize" | "delete") {
    setError(""); setSuccess("");
    setFileErrors(current => ({ ...current, [item.id]: "" }));
    setBusyIds(current => ({ ...current, [item.id]: true }));
    try {
      if (action === "delete") {
        if (!window.confirm(`Remove ${item.original_filename}? Finalized academic content is never deleted.`)) return;
        await api<void>(`/teacher/textbooks/${textbookId}/files/${item.id}`, { method: "DELETE" });
      } else if (action === "detect") {
        if (item.status === "ready" && !window.confirm(`Re-detect ${item.original_filename} and replace its current unused chapter index? This is blocked if the chapters have been used for generation.`)) return;
        const detected = await api<{ file: TextbookFile }>(`/teacher/textbooks/${textbookId}/files/${item.id}/detect`, { method: "POST" });
        setReviews(current => ({ ...current, [item.id]: detected.file.detected_chapters.map(chapter => ({ ...chapter })) }));
      } else {
        const chapters = reviews[item.id] ?? [];
        if (!chapters.length) {
          setFileErrors(current => ({ ...current, [item.id]: "Add at least one chapter before finalizing." }));
          return;
        }
        await api(`/teacher/textbooks/${textbookId}/files/${item.id}/finalize`, {
          method: "POST",
          body: JSON.stringify({ chapters: chapters.map(({ code, title, page_start, page_end }) => ({ code, title, page_start, page_end })) }),
        });
        setSuccess(`${item.original_filename} was indexed and is available for question generation.`);
      }
      await loadFiles();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Textbook file action failed";
      setFileErrors(current => ({ ...current, [item.id]: message }));
      await loadFiles();
    } finally {
      setBusyIds(current => ({ ...current, [item.id]: false }));
    }
  }

  async function createCatalog(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    try {
      const result = await api<{ textbook: ManagedTextbook; created: boolean }>("/teacher/textbooks/catalog", {
        method: "POST",
        body: JSON.stringify({
          board, state_code: board === "state" ? stateCode : null, class_level: classLevel,
          subject_code: newSubjectCode, subject_title: newSubjectTitle,
          title: newTextbookTitle, academic_year: academicYear || null, edition,
        }),
      });
      const params = new URLSearchParams({ board, class_level: String(classLevel) });
      if (board === "state") params.set("state_code", stateCode.trim());
      const subjectData = await api<{ items: Subject[] }>(`/curriculum/subjects?${params}`);
      setSubjects(subjectData.items);
      const sameSubject = subjectId === result.textbook.subject_id;
      pendingTextbookId.current = result.textbook.id;
      setSubjectId(result.textbook.subject_id);
      const [bookData, termData] = await Promise.all([
        api<{ items: Textbook[] }>(`/curriculum/subjects/${result.textbook.subject_id}/textbooks`),
        api<{ items: Term[] }>(`/curriculum/terms?subject_id=${result.textbook.subject_id}`),
      ]);
      setTextbooks(bookData.items); setTerms(termData.items);
      if (sameSubject) { setTextbookId(result.textbook.id); pendingTextbookId.current = ""; }
      setSuccess(result.created ? "Textbook record created and selected. Choose or create its term." : "That textbook already exists and is now selected.");
      setNewTextbookTitle(""); setAcademicYear(""); setEdition("current");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Textbook could not be created"); }
  }

  async function createTerm(event: FormEvent) {
    event.preventDefault(); setError(""); setSuccess("");
    if (!textbookId) { setError("Select a textbook first."); return; }
    try {
      const result = await api<{ term: Term; created: boolean }>(`/teacher/textbooks/${textbookId}/terms`, {
        method: "POST", body: JSON.stringify({ code: newTermCode, title: newTermTitle }),
      });
      const data = await api<{ items: Term[] }>(`/curriculum/terms?subject_id=${subjectId}`);
      setTerms(data.items); setTermId(result.term.id); setNewTermCode(""); setNewTermTitle("");
      setSuccess(result.created ? "Term created and selected." : "That term already exists and is now selected.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Term could not be created"); }
  }

  return <>
    <div className="page-header"><div><p className="eyebrow">Curriculum sources</p><h1>Manage Textbooks</h1><p className="muted">Upload several private PDFs, verify detected chapter boundaries, then approve indexing for question generation.</p></div></div>
    {error && <Notice kind="error">{error}</Notice>}{success && <Notice kind="success">{success}</Notice>}

    <section className="card stack">
      <div><h2>1. Select curriculum and textbook</h2><p className="muted">Every uploaded file is isolated to this exact board, class, subject, textbook, and term.</p></div>
      <div className="grid three">
        <label>Board<select value={board} onChange={event => setBoard(event.target.value as BoardCode)}>{boards.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label>
        {board === "state" && <label>State / curriculum identifier<input value={stateCode} onChange={event => setStateCode(event.target.value)} placeholder="e.g. tamil-nadu" /></label>}
        <label>Class<select value={classLevel} onChange={event => setClassLevel(Number(event.target.value))}>{classes.map(item => <option key={item} value={item}>Class {item}</option>)}</select></label>
        <label>Subject<select value={subjectId} onChange={event => setSubjectId(event.target.value)}><option value="">Choose subject</option>{subjects.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        <label>Textbook<select disabled={!subjectId} value={textbookId} onChange={event => setTextbookId(event.target.value)}><option value="">Choose textbook</option>{textbooks.map(item => <option key={item.id} value={item.id}>{item.title} ({item.edition})</option>)}</select></label>
        <label>Term<select disabled={!textbookId} value={termId} onChange={event => setTermId(event.target.value)}><option value="">Choose term</option>{terms.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
      </div>
      {subjectId && textbooks.length === 0 && <Empty>No textbook is configured for this subject. Create one below before uploading source PDFs.</Empty>}
      {selectedTextbook && <div className="availability-row"><Pill>{selectedTextbook.processing_status}</Pill><span>{selectedTextbook.title} · {selectedTextbook.indexed_chunk_count} indexed chunks</span></div>}
    </section>

    <details className="card textbook-setup">
      <summary>Create a textbook or term</summary>
      <div className="grid two textbook-setup-grid">
        <form className="stack" onSubmit={createCatalog}><h3>New textbook record</h3><p className="muted">Uses the board and class selected above.</p>
          <label>Subject identifier<input required value={newSubjectCode} onChange={event => setNewSubjectCode(event.target.value)} placeholder="e.g. mathematics" /></label>
          <label>Subject name<input required value={newSubjectTitle} onChange={event => setNewSubjectTitle(event.target.value)} placeholder="e.g. Mathematics" /></label>
          <label>Textbook title<input required value={newTextbookTitle} onChange={event => setNewTextbookTitle(event.target.value)} /></label>
          <div className="grid two"><label>Academic year (optional)<input value={academicYear} onChange={event => setAcademicYear(event.target.value)} /></label><label>Edition<input required value={edition} onChange={event => setEdition(event.target.value)} /></label></div>
          <button type="submit">Create textbook</button>
        </form>
        <form className="stack" onSubmit={createTerm}><h3>New term</h3><p className="muted">Terms are shared by textbooks in the selected subject.</p>
          <label>Term identifier<input required value={newTermCode} onChange={event => setNewTermCode(event.target.value)} placeholder="e.g. term_1" /></label>
          <label>Term name<input required value={newTermTitle} onChange={event => setNewTermTitle(event.target.value)} placeholder="e.g. Term 1" /></label>
          <button type="submit" disabled={!textbookId}>Create term</button>
        </form>
      </div>
    </details>

    <section className="card stack textbook-upload-card">
      <div><h2>2. Upload PDF files</h2><p className="muted">Choose all chapter PDFs for the selected term. Each file uploads and processes independently.</p></div>
      <form className="stack" onSubmit={uploadAll}>
        <label>Private textbook PDFs<input ref={inputRef} multiple accept="application/pdf,.pdf" type="file" disabled={!textbookId || !termId || uploading} onChange={event => chooseFiles(event.target.files)} /></label>
        {localUploads.length > 0 && <div className="upload-queue">{localUploads.map((item, index) => <div className="upload-queue-row" key={`${item.name}-${index}`}><strong>{item.name}</strong><span><Pill>{item.status}</Pill>{item.error && <small>{item.error}</small>}</span></div>)}</div>}
        <div className="actions"><button disabled={!selectedFiles.length || !textbookId || !termId || uploading}>{uploading ? "Uploading and detecting..." : `${localUploads.some(item => item.status === "failed") ? "Retry" : "Upload"} ${selectedFiles.length || ""} PDF${selectedFiles.length === 1 ? "" : "s"}`}</button><span className="muted">Maximum size is enforced per file by the backend.</span></div>
      </form>
    </section>

    <section className="stack textbook-review-section">
      <div><h2>3. Review detected chapters</h2><p className="muted">Chapter numbers and titles come from PDF text, never filenames. Confirm or correct them before finalizing.</p></div>
      {!textbookId || !termId ? <Empty>Select a textbook and term to view its uploaded files.</Empty> : files === null ? <Spinner /> : files.length === 0 ? <Empty>No PDFs have been uploaded for this textbook and term.</Empty> : files.map(item => {
        const chapters = reviews[item.id] ?? [];
        const immutable = item.status === "ready";
        return <article className="card textbook-file-card" key={item.id}>
          <div className="textbook-file-heading"><div><h3>{item.original_filename}</h3><p className="muted">{fileSize(item.byte_size)}{item.page_count ? ` · ${item.page_count} pages` : ""}</p></div><Pill>{busyIds[item.id] ? "processing" : item.status}</Pill></div>
          {fileErrors[item.id] && <Notice kind="error">{fileErrors[item.id]}</Notice>}
          {item.failure_reason && <Notice kind={item.status === "failed" ? "error" : "info"}>{item.failure_reason}</Notice>}
          {(item.status === "review_required" || immutable) && <div className="chapter-review-list">
            {chapters.length === 0 ? <Empty>No chapter heading was detected. Add the chapter number, title, and PDF page range manually.</Empty> : chapters.map((chapter, index) => <div className="chapter-review-row" key={`${item.id}-${index}`}>
              <label>Chapter number<input disabled={immutable} value={chapter.code} onChange={event => setReviewChapter(item.id, index, "code", event.target.value)} /></label>
              <label>Chapter title<input disabled={immutable} value={chapter.title} onChange={event => setReviewChapter(item.id, index, "title", event.target.value)} /></label>
              <label>Start page<input disabled={immutable} type="number" min={1} max={item.page_count ?? undefined} value={chapter.page_start} onChange={event => setReviewChapter(item.id, index, "page_start", event.target.value)} /></label>
              <label>End page<input disabled={immutable} type="number" min={1} max={item.page_count ?? undefined} value={chapter.page_end} onChange={event => setReviewChapter(item.id, index, "page_end", event.target.value)} /></label>
              {!immutable && <button type="button" className="danger chapter-remove" onClick={() => removeChapter(item.id, index)}>Remove</button>}
            </div>)}
          </div>}
          <div className="actions">
            {item.status === "review_required" && <><button type="button" className="secondary" disabled={busyIds[item.id]} onClick={() => void fileAction(item, "detect")}>Re-detect chapters</button><button type="button" className="secondary" disabled={busyIds[item.id]} onClick={() => addChapter(item)}>Add chapter</button><button type="button" disabled={busyIds[item.id]} onClick={() => void fileAction(item, "finalize")}>Approve and index</button></>}
            {item.status === "failed" && <button type="button" disabled={busyIds[item.id]} onClick={() => void fileAction(item, "detect")}>Retry detection</button>}
            {item.status === "ready" && <button type="button" className="secondary" disabled={busyIds[item.id]} onClick={() => void fileAction(item, "detect")}>Re-detect and replace unused index</button>}
            {!immutable && <button type="button" className="danger" disabled={busyIds[item.id]} onClick={() => void fileAction(item, "delete")}>Remove file</button>}
          </div>
        </article>;
      })}
    </section>
  </>;
}
