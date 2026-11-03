"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { TeacherTestSummary } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

export default function TestsPage() {
  const [items, setItems] = useState<TeacherTestSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ items: TeacherTestSummary[] }>("/tests")
      .then(response => setItems(response.items))
      .catch(caught => setError(caught instanceof Error ? caught.message : "Tests could not be loaded"));
  }, []);

  return <>
    <div className="page-header"><div><p className="eyebrow">Teacher workspace</p><h1>Tests</h1><p className="muted">Open any existing test to review its assignments or add newly onboarded students.</p></div><Link className="button" href="/teacher/generate">Generate a test</Link></div>
    {error && <Notice kind="error">{error}</Notice>}
    <section className="card">
      {items === null && !error ? <Spinner label="Loading tests..." /> : !items?.length ? <Empty>No tests have been created yet.</Empty> : <div className="table-wrap"><table>
        <thead><tr><th>Test</th><th>Curriculum</th><th>Status</th><th>Marks</th><th>Assigned</th><th>Attempts</th><th>Created</th><th>Actions</th></tr></thead>
        <tbody>{items.map(test => <tr key={test.id}><td><strong>{test.title}</strong></td><td>{test.board === "state" ? `State (${test.state_code})` : test.board.toUpperCase()} · Class {test.class_level} · {test.subject_title}</td><td><Pill>{test.status}</Pill></td><td>{test.total_marks}</td><td>{test.assigned_count}</td><td>{test.attempt_count}</td><td>{new Date(test.created_at).toLocaleDateString()}</td><td><Link className="button secondary" href={`/teacher/tests/${test.id}`}>Open</Link></td></tr>)}</tbody>
      </table></div>}
    </section>
  </>;
}
