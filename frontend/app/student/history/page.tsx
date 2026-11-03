"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { StudentHistoryItem } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

export default function StudentHistoryPage() {
  const [items, setItems] = useState<StudentHistoryItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ items: StudentHistoryItem[] }>("/student/test-history")
      .then(response => setItems(response.items))
      .catch(caught => setError(caught instanceof Error ? caught.message : "Test history could not be loaded"));
  }, []);

  return <>
    <div className="page-header"><div><p className="eyebrow">My academic record</p><h1>My Test History</h1><p className="muted">Assigned, ongoing, submitted, evaluated and published tests are shown together.</p></div></div>
    {error && <Notice kind="error">{error}</Notice>}
    <section className="card">
      {items === null && !error ? <Spinner label="Loading test history..." /> : !items?.length ? <Empty>No tests have been assigned yet.</Empty> : <div className="table-wrap"><table>
        <thead><tr><th>Test</th><th>Curriculum</th><th>Date</th><th>Progress</th><th>Marks</th><th>Status</th><th>Action</th></tr></thead>
        <tbody>{items.map(item => <tr key={item.test_id}><td><strong>{item.test_name}</strong></td><td>{item.board === "state" ? `State (${item.state_code})` : item.board.toUpperCase()} · Class {item.class_level} · {item.subject_title}</td><td>{new Date(item.date).toLocaleString()}</td><td>{item.answered_count} answered · {item.unanswered_count} unanswered</td><td>{item.result_published ? `${item.obtained_marks}/${item.total_marks}` : "Not published"}</td><td><Pill>{item.status.replaceAll("_", " ")}</Pill></td><td>{item.result_published && item.attempt_id ? <Link className="button secondary" href={`/student/results/${item.attempt_id}`}>View result</Link> : item.status === "assigned" ? <Link className="button secondary" href={`/student/tests/${item.test_id}`}>View test</Link> : item.status === "in_progress" && item.attempt_id ? <Link className="button secondary" href={`/student/attempts/${item.attempt_id}`}>Continue</Link> : <span className="muted">Awaiting publication</span>}</td></tr>)}</tbody>
      </table></div>}
    </section>
  </>;
}
