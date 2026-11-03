"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { TeacherHistoryItem } from "@/lib/types";
import { Empty, Notice, Pill, Spinner } from "@/components/Ui";

interface HistoryResponse {
  items: TeacherHistoryItem[];
  total: number;
  limit: number;
  offset: number;
  student: { id: string; name: string; login_identifier: string; school_name: string | null; school_location: string | null } | null;
}

const PAGE_SIZE = 50;

function TeacherHistoryContent() {
  const searchParams = useSearchParams();
  const studentId = searchParams.get("student_id");
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => { setOffset(0); }, [studentId]);
  useEffect(() => {
    const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (studentId) query.set("student_id", studentId);
    api<HistoryResponse>(`/teacher/test-history?${query.toString()}`)
      .then(setData)
      .catch(caught => setError(caught instanceof Error ? caught.message : "Test history could not be loaded"));
  }, [studentId, offset]);

  return <>
    <div className="page-header"><div><p className="eyebrow">Permanent academic record</p><h1>{data?.student ? `${data.student.name}'s Test History` : "Test History"}</h1><p className="muted">All attempts and published results remain available from PostgreSQL across sign-ins and server restarts.</p>{data?.student && <p>{[data.student.school_name, data.student.school_location].filter(Boolean).join(" · ") || "School not provided"}</p>}</div>{studentId && <Link className="button secondary" href="/teacher/history">View all students</Link>}</div>
    {error && <Notice kind="error">{error}</Notice>}
    <section className="card">
      {!data && !error ? <Spinner label="Loading test history..." /> : !data?.items.length ? <Empty>No attempts are recorded for this selection.</Empty> : <div className="table-wrap"><table>
        <thead><tr><th>Student</th><th>Test</th><th>Date</th><th>Total</th><th>Obtained</th><th>Answered</th><th>Unanswered</th><th>Status</th><th>Details</th></tr></thead>
        <tbody>{data.items.map(item => <tr key={item.attempt_id}><td><Link href={`/teacher/history?student_id=${item.student_id}`}><strong>{item.student_name}</strong></Link></td><td>{item.test_name}</td><td>{new Date(item.date).toLocaleString()}</td><td>{item.total_marks}</td><td>{item.obtained_marks ?? "—"}</td><td>{item.answered_count}</td><td>{item.unanswered_count}</td><td><Pill>{item.status.replaceAll("_", " ")}</Pill></td><td>{item.status === "in_progress" ? <span className="muted">Available after submission</span> : <Link className="button secondary" href={`/teacher/evaluations/${item.attempt_id}`}>View answers</Link>}</td></tr>)}</tbody>
      </table></div>}
      {data && data.total > PAGE_SIZE && <div className="student-pagination"><span>{data.offset + 1}-{Math.min(data.offset + data.items.length, data.total)} of {data.total}</span><div className="actions"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Previous</button><button className="secondary" disabled={offset + data.items.length >= data.total} onClick={() => setOffset(value => value + PAGE_SIZE)}>Next</button></div></div>}
    </section>
  </>;
}

export default function TeacherHistoryPage() {
  return <Suspense fallback={<Spinner label="Loading test history..." />}><TeacherHistoryContent /></Suspense>;
}
