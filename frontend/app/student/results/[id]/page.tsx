"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { ResultDetail } from "@/lib/types";
import { Notice, Pill, Spinner } from "@/components/Ui";

export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ResultDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<ResultDetail>(`/student/results/${id}`).then(setData).catch(caught => setError(caught.message)); }, [id]);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data) return <Spinner />;
  return <><div className="page-header"><div><p className="eyebrow">Published result</p><h1>{data.test_title ?? "Test result"}</h1><p>Published {new Date(data.published_at).toLocaleString()}</p></div></div>
    <section className="grid three"><div className="card kpi"><span>Marks</span><strong>{data.awarded_total}/{data.max_total}</strong></div><div className="card kpi"><span>Percentage</span><strong>{Number(data.percentage).toFixed(1)}%</strong></div><div className="card"><p className="muted">Every mark was entered manually by your teacher.</p></div></section>
    {data.overall_comment && <Notice>Teacher comment: {data.overall_comment}</Notice>}
    <section className="stack" style={{ marginTop: "1rem" }}>{data.questions.map(question => <article className="card" key={question.test_question_id}><div className="question-meta"><strong>Question {question.order}</strong><Pill>{question.status}</Pill><span className="marks">{question.awarded_marks}/{question.max_marks}</span></div><p style={{ whiteSpace: "pre-wrap" }}>{question.question_text}</p>
      <div className="card"><strong>Your submitted answer</strong>{question.question_type === "mcq" ? <p>{question.options?.find(option => option.id === question.answer?.selected_option_id)?.text ?? "Unanswered"}</p> : <p style={{ whiteSpace: "pre-wrap" }}>{question.answer?.text_answer || "No typed answer"}</p>}
        {!!question.answer?.images?.length && <div className="image-grid">{question.answer.images.map((image, index) => <a className="image-card" href={image.preview_url} target="_blank" rel="noreferrer" key={image.id}><img src={image.preview_url} alt={`Submitted notebook page ${index + 1}`} /><span>Open page {index + 1}</span></a>)}</div>}
      </div>{question.feedback && <Notice>Teacher feedback: {question.feedback}</Notice>}</article>)}</section>
  </>;
}
