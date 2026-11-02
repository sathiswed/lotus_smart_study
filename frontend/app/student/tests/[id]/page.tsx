"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { StudentQuestion } from "@/lib/types";
import { Notice, Spinner } from "@/components/Ui";

interface StudentTest {
  id: string;
  title: string;
  instructions: string;
  total_marks: number;
  board_label?: string | null;
  class_level?: number | null;
  subject_label?: string | null;
  textbook_label?: string | null;
  questions: StudentQuestion[];
}

export default function TestInstructionsPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<StudentTest | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  useEffect(() => { api<StudentTest>(`/student/tests/${id}`).then(setData).catch(caught => setError(caught.message)); }, [id]);
  async function start() {
    setBusy(true);
    try {
      const attempt = await api<{ id: string }>(`/student/tests/${id}/attempts`, { method: "POST" });
      router.push(`/student/attempts/${attempt.id}`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to start test"); }
    finally { setBusy(false); }
  }
  if (!data) return error ? <Notice kind="error">{error}</Notice> : <Spinner />;
  return <>
    <div className="page-header"><div><p className="eyebrow">Test instructions</p><h1>{data.title}</h1><p>{data.questions.length} questions | {data.total_marks} marks</p>{data.board_label && <p className="muted">{data.board_label} | Class {data.class_level} | {data.subject_label} | {data.textbook_label}</p>}</div></div>
    {error && <Notice kind="error">{error}</Notice>}
    <section className="card"><h2>Before you start</h2><p>{data.instructions || "Answer each question and submit when finished."}</p><ul><li>MCQ and typed answers save automatically.</li><li>You can upload ordered notebook photos where needed.</li><li>Wait for every save and upload to finish before submitting.</li><li>After submission, answers become read-only.</li></ul><button onClick={() => void start()} disabled={busy}>{busy ? "Starting..." : "Start test"}</button></section>
  </>;
}
