"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { StudentDashboard } from "@/lib/types";
import { Empty, MetricCard, Notice, Pill, Spinner } from "@/components/Ui";

function scopeLabel(test: { board?: string; state_code?: string | null; class_level?: number; subject_title?: string }) {
  const board = test.board === "state" ? `State Board${test.state_code ? ` (${test.state_code})` : ""}` : test.board?.toUpperCase();
  return [board, test.class_level ? `Class ${test.class_level}` : null, test.subject_title].filter(Boolean).join(" | ");
}

export default function StudentDashboardPage() {
  const [data, setData] = useState<StudentDashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<StudentDashboard>("/student/dashboard").then(setData).catch(caught => setError(caught.message)); }, []);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data) return <Spinner />;
  return <><div className="page-header"><div><p className="eyebrow">Student workspace</p><h1>My tests</h1><p className="muted">Your assigned textbook-grounded assessments</p></div><Link className="button secondary" href="/student/history">View full history</Link></div>
    <section className="grid two"><MetricCard label="Available tests" value={data.available_tests.length} icon="available" /><MetricCard label="Completed results" value={data.completed_tests.length} icon="result" positive /></section>
    <section className="card" style={{ marginTop: "1rem" }}><h2>Available tests</h2>{!data.available_tests.length ? <Empty>No tests are currently assigned.</Empty> : <div className="list">{data.available_tests.map(test => <div className="list-row" key={test.id}><div><strong>{test.title}</strong><div>{scopeLabel(test)} | {test.total_marks} marks {test.attempt_status && <>- <Pill>{test.attempt_status.replaceAll("_", " ")}</Pill></>}</div></div><Link className="button" href={test.attempt_id ? `/student/attempts/${test.attempt_id}` : `/student/tests/${test.id}`}>{test.attempt_id ? "Continue" : "View instructions"}</Link></div>)}</div>}</section>
    {!!data.submitted_tests?.length && <section className="card" style={{ marginTop: "1rem" }}><h2>Submitted tests</h2><div className="list">{data.submitted_tests.map(test => <div className="list-row" key={test.attempt_id}><div><strong>{test.title}</strong><div>{scopeLabel(test)} | <Pill>{test.attempt_status?.replaceAll("_", " ") ?? "submitted"}</Pill></div></div><span>Awaiting published result</span></div>)}</div></section>}
    <section className="card" style={{ marginTop: "1rem" }}><h2>Completed tests</h2>{!data.completed_tests.length ? <Empty>Published results will appear here after teacher evaluation.</Empty> : <div className="list">{data.completed_tests.map(test => <div className="list-row" key={test.attempt_id}><div><strong>{test.title}</strong><div>{scopeLabel(test)} | {test.awarded_total}/{test.max_total} marks - {Number(test.percentage).toFixed(1)}%</div></div>{test.attempt_id && <Link className="button secondary" href={`/student/results/${test.attempt_id}`}>View result</Link>}</div>)}</div>}</section>
  </>;
}
