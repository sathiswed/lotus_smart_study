"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BoardCode, BoardOption, Chapter, Curriculum, Subject, Textbook, Topic } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

const questionTypes = [
  ["mcq", "MCQ", 1], ["one_mark", "1-mark", 1], ["two_mark", "2-mark", 2],
  ["three_mark", "3-mark", 3], ["five_mark", "5-mark", 5], ["case_study", "Case study", 5],
] as const;
const MAX_PER_TYPE = 10;
const MAX_TOTAL = 20;

export default function GeneratePage() {
  const [boards, setBoards] = useState<BoardOption[]>([]);
  const [classes, setClasses] = useState<number[]>([]);
  const [board, setBoard] = useState<BoardCode>("cbse");
  const [classLevel, setClassLevel] = useState(8);
  const [stateCode, setStateCode] = useState("");
  const [curriculum, setCurriculum] = useState<Curriculum | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [textbooks, setTextbooks] = useState<Textbook[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [textbookId, setTextbookId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [counts, setCounts] = useState<Record<string, number>>(Object.fromEntries(questionTypes.map(([key]) => [key, 0])));
  const [marks, setMarks] = useState<Record<string, number>>(Object.fromEntries(questionTypes.map(([key, , value]) => [key, value])));
  const [difficulty, setDifficulty] = useState("mixed");
  const [style, setStyle] = useState("standard");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  useEffect(() => {
    api<{ boards: BoardOption[]; classes: number[] }>("/curriculum/options")
      .then(response => { setBoards(response.boards); setClasses(response.classes); })
      .catch(caught => setError(caught.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setCurriculum(null); setSubjects([]); setSubjectId(""); setTextbooks([]); setTextbookId(""); setChapters([]); setChapterId(""); setTopics([]); setTopicId("");
    const normalizedState = stateCode.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    if (board === "state" && !normalizedState) return;
    const params = new URLSearchParams({ board, class_level: String(classLevel) });
    if (normalizedState) params.set("state_code", normalizedState);
    api<{ curriculum: Curriculum | null; items: Subject[] }>(`/curriculum/subjects?${params}`)
      .then(response => { setCurriculum(response.curriculum); setSubjects(response.items); })
      .catch(caught => setError(caught.message));
  }, [board, classLevel, stateCode]);

  useEffect(() => {
    setTextbooks([]); setTextbookId(""); setChapters([]); setChapterId(""); setTopics([]); setTopicId("");
    if (!subjectId) return;
    api<{ items: Textbook[] }>(`/curriculum/subjects/${subjectId}/textbooks`).then(response => setTextbooks(response.items)).catch(caught => setError(caught.message));
  }, [subjectId]);

  useEffect(() => {
    setChapters([]); setChapterId(""); setTopics([]); setTopicId("");
    if (!textbookId) return;
    api<{ items: Chapter[] }>(`/curriculum/textbooks/${textbookId}/chapters`).then(response => setChapters(response.items)).catch(caught => setError(caught.message));
  }, [textbookId]);

  useEffect(() => {
    setTopics([]); setTopicId("");
    if (!chapterId) return;
    api<{ items: Topic[] }>(`/curriculum/chapters/${chapterId}/topics`).then(response => setTopics(response.items.filter(item => item.is_enabled !== false))).catch(caught => setError(caught.message));
  }, [chapterId]);

  const selectedBook = textbooks.find(item => item.id === textbookId);
  const selectedChapter = chapters.find(item => item.id === chapterId);
  const sourceReady = Boolean(selectedBook?.content_available && selectedChapter?.content_available);
  const totalQuestions = useMemo(() => Object.values(counts).reduce((sum, value) => sum + value, 0), [counts]);
  const totalMarks = useMemo(() => questionTypes.reduce((sum, [key]) => sum + (counts[key] ?? 0) * (marks[key] ?? 0), 0), [counts, marks]);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (!textbookId || !chapterId || !sourceReady || totalQuestions < 1) { setError("Select an indexed textbook and chapter, then request at least one question."); return; }
    if (totalQuestions > MAX_TOTAL) { setError(`Request no more than ${MAX_TOTAL} questions per batch.`); return; }
    setBusy(true);
    try {
      const batch = await api<{ id: string }>("/generation-batches", { method: "POST", body: JSON.stringify({ textbook_id: textbookId, chapter_id: chapterId, topic_id: topicId || null, counts, marks, difficulty, style }) });
      router.push(`/teacher/batches/${batch.id}`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Generation setup failed"); setBusy(false); }
  }

  if (loading) return <Spinner label="Loading curriculum options..." />;
  return <>
    <div className="page-header"><div><p className="eyebrow">Curriculum-grounded generation</p><h1>Question &amp; Test Generation</h1><p className="muted">Select an exact board, class, subject, textbook and chapter. Generation never broadens beyond that source.</p></div><Link className="button secondary" href="/teacher/textbooks">Manage textbooks</Link></div>
    {error && <Notice kind="error">{error}</Notice>}
    <form onSubmit={submit} className="stack">
      <section className="card"><h2>Curriculum and textbook</h2><div className="grid three">
        <label>Board<select value={board} onChange={event => setBoard(event.target.value as BoardCode)}>{boards.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label>
        {board === "state" && <label>State / curriculum identifier<input required value={stateCode} onChange={event => setStateCode(event.target.value)} placeholder="e.g. tamil-nadu" /></label>}
        <label>Class<select value={classLevel} onChange={event => setClassLevel(Number(event.target.value))}>{classes.map(item => <option key={item} value={item}>Class {item}</option>)}</select></label>
        <label>Subject<select value={subjectId} onChange={event => setSubjectId(event.target.value)} disabled={!subjects.length}><option value="">Choose subject</option>{subjects.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        <label>Textbook<select value={textbookId} onChange={event => setTextbookId(event.target.value)} disabled={!subjectId || !textbooks.length}><option value="">Choose textbook</option>{textbooks.map(item => <option key={item.id} value={item.id}>{item.title} ({item.processing_status})</option>)}</select></label>
        <label>Chapter<select value={chapterId} onChange={event => setChapterId(event.target.value)} disabled={!textbookId || !chapters.length}><option value="">Choose chapter</option>{chapters.map(item => <option key={item.id} value={item.id} disabled={!item.content_available}>{item.term_title ? `${item.term_title} - ` : ""}{item.code}. {item.title}{item.content_available ? "" : " (not indexed)"}</option>)}</select></label>
        <label>Topic (optional)<select value={topicId} onChange={event => setTopicId(event.target.value)} disabled={!chapterId || !topics.length}><option value="">Whole chapter</option>{topics.map(item => <option key={item.id} value={item.id}>{item.section_code} {item.title}</option>)}</select></label>
      </div>
      {!curriculum || subjects.length === 0 ? <Empty>No subjects or textbooks are configured for this board and class. Upload curriculum material to continue.</Empty> : subjectId && textbooks.length === 0 ? <Empty>No textbooks have been uploaded for this subject.</Empty> : selectedBook && <div className="availability-row"><Pill>{selectedBook.processing_status}</Pill><span>{selectedBook.content_available ? `${selectedBook.indexed_chunk_count} indexed source sections available` : "Generation remains disabled until extraction and indexing are complete."}</span></div>}
      </section>
      <section className="card"><h2>Question pattern</h2><div className="question-pattern-grid"><strong>Question type</strong><strong>Count</strong><strong>Marks each</strong>{questionTypes.map(([key, label]) => <div className="question-pattern-row" key={key}><span>{label}</span><input aria-label={`${label} count`} type="number" min="0" max={MAX_PER_TYPE} value={counts[key]} onChange={event => setCounts(current => ({ ...current, [key]: Math.min(MAX_PER_TYPE, Math.max(0, Number(event.target.value) || 0)) }))} /><input aria-label={`${label} marks`} type="number" min="1" max="100" value={marks[key]} onChange={event => setMarks(current => ({ ...current, [key]: Math.min(100, Math.max(1, Number(event.target.value) || 1)) }))} /></div>)}</div><p><strong>{totalQuestions}</strong> of {MAX_TOTAL} questions | <strong>{totalMarks}</strong> calculated marks</p></section>
      <section className="card"><h2>Difficulty and framing</h2><div className="grid two"><label>Difficulty<select value={difficulty} onChange={event => setDifficulty(event.target.value)}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option><option value="mixed">Mixed</option></select></label><label>Style<select value={style} onChange={event => setStyle(event.target.value)}><option value="standard">Standard</option><option value="cbse_style">Board-style framing</option><option value="challenging">Challenging</option></select></label></div><p className="muted">Framing preferences do not claim authoritative board-pattern grounding unless approved reference material exists.</p></section>
      <button disabled={busy || !sourceReady || totalQuestions < 1 || totalQuestions > MAX_TOTAL}>{busy ? "Creating..." : "Create generation batch"}</button>
    </form>
  </>;
}
