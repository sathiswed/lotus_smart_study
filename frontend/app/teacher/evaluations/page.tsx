"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { EvaluationQueueItem } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

export default function EvaluationsPage() {
  const [items, setItems] = useState<EvaluationQueueItem[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<{ items: EvaluationQueueItem[] }>("/teacher/evaluations").then(response => setItems(response.items)).catch(caught => setError(caught.message)); }, []);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!items) return <Spinner />;
  return <><div className="page-header"><div><p className="eyebrow">Manual evaluation</p><h1>Pending evaluations</h1><p className="muted">Every answer, including MCQs, is marked by a teacher.</p></div></div>
    <section className="card">{!items.length ? <Empty>No submitted attempts are waiting.</Empty> : <div className="list">{items.map(item => <div className="list-row" key={item.attempt_id}>
      <div><strong>{item.test_title}</strong><div>{item.student_name} - <Pill>{item.status.replaceAll("_", " ")}</Pill></div><small>Submitted {new Date(item.submitted_at).toLocaleString()}</small></div>
      <Link className="button" href={`/teacher/evaluations/${item.attempt_id}`}>Evaluate</Link>
    </div>)}</div>}</section></>;
}
