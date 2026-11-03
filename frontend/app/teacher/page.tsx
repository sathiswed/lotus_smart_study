"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { GenerationBatchSummary, TeacherDashboard } from "@/lib/types";
import { Empty, MetricCard, Notice, Pill, Spinner } from "@/components/Ui";

export default function TeacherDashboardPage() {
  const [data, setData] = useState<TeacherDashboard | null>(null);
  const [batches, setBatches] = useState<GenerationBatchSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api<TeacherDashboard>("/teacher/dashboard"),
      api<{ items: GenerationBatchSummary[] }>("/generation-batches"),
    ]).then(([dashboard, recentBatches]) => {
      setData(dashboard);
      setBatches(recentBatches.items);
    }).catch(caught => setError(caught.message));
  }, []);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data) return <Spinner />;
  return <>
    <div className="page-header"><div><p className="eyebrow">Teacher workspace</p><h1>Dashboard</h1><p className="muted">Create textbook-grounded tests and continue pending evaluation.</p></div><Link className="button" href="/teacher/generate">Generate a test</Link></div>
    <section className="grid four" aria-label="Key performance indicators"><MetricCard label="Total tests" value={data.total_tests} icon="tests" /><MetricCard label="Published" value={data.published_tests} icon="publish" positive /><MetricCard label="Submitted" value={data.submitted_attempts} icon="submit" /><MetricCard label="Pending evaluation" value={data.pending_evaluation} icon="review" /></section>
    <section className="card" style={{ marginTop: "1rem" }}><div className="page-header"><h2>Recent generation batches</h2><Link href="/teacher/generate">New batch</Link></div>{batches.length === 0 ? <Empty>No generation batches yet.</Empty> : <div className="list">{batches.map(batch => <div className="list-row" key={batch.id}><div><strong>{batch.textbook_title ? `${batch.textbook_title}: ` : ""}{batch.chapter_title}</strong><div><Pill>{batch.status}</Pill> | {batch.calculated_marks} marks{batch.topic_title ? ` | ${batch.topic_title}` : ""}</div></div><Link className="button secondary" href={`/teacher/batches/${batch.id}`}>Open</Link></div>)}</div>}</section>
    <section className="card" style={{ marginTop: "1rem" }}><div className="page-header"><h2>Recent tests</h2><div className="actions"><Link href="/teacher/tests">All tests</Link><Link href="/teacher/history">Test history</Link><Link href="/teacher/evaluations">Pending evaluations</Link></div></div>{data.recent_tests.length === 0 ? <Empty>No tests yet. Generate the first textbook-grounded test.</Empty> : <div className="list">{data.recent_tests.map(test => <div className="list-row" key={test.id}><div><strong>{test.title}</strong><div>{test.board === "state" ? `State Board (${test.state_code})` : test.board?.toUpperCase()} | Class {test.class_level} | {test.subject_title}</div><div><Pill>{test.status}</Pill> | {test.total_marks} marks</div></div><Link className="button secondary" href={`/teacher/tests/${test.id}`}>Open</Link></div>)}</div>}</section>
  </>;
}
