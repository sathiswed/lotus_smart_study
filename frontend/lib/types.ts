export type Role = "teacher" | "student";
export type QuestionType = "mcq" | "one_mark" | "two_mark" | "three_mark" | "five_mark" | "case_study";
export type QuestionStatus = "draft" | "approved" | "rejected";
export type AttemptStatus = "in_progress" | "submitted" | "evaluation_in_progress" | "evaluated" | "result_published";
export type EvaluationStatus = "correct" | "wrong" | "partial";

export interface User { id: string; name: string; login_identifier: string; role: Role; must_change_password: boolean }
export type BoardCode = "cbse" | "state" | "icse";
export interface BoardOption { code: BoardCode; title: string; requires_state: boolean }
export interface Curriculum { id: string; code: string; board: BoardCode; state_code: string | null; class_level: number }
export interface Subject { id: string; curriculum_id: string; code: string; title: string }
export interface Textbook { id: string; subject_id: string; title: string; academic_year?: string | null; edition: string; processing_status: string; failure_reason?: string | null; content_available: boolean; indexed_chunk_count: number }
export interface ManagedTextbook extends Textbook { curriculum_id: string; board: BoardCode; state_code: string | null; class_level: number; subject_code: string; subject_title: string }
export interface Term { id: string; subject_id?: string; code: string; title: string; sequence: number }
export interface DetectedTextbookChapter { code: string; title: string; page_start: number; page_end: number; confidence?: "high" | "medium" | "low" }
export interface TextbookFile {
  id: string; textbook_id: string; term_id: string; original_filename: string;
  byte_size: number; page_count: number | null;
  status: "uploading" | "review_required" | "indexing" | "ready" | "failed";
  detected_chapters: DetectedTextbookChapter[];
  approved_chapters: DetectedTextbookChapter[];
  failure_reason: string | null; created_at: string; updated_at: string;
}
export interface Chapter { id: string; textbook_id: string; term_id: string; term_title?: string; code: string; title: string; sequence: number; content_available?: boolean }
export interface Topic { id: string; chapter_id: string; section_code: string; title: string; sequence: number; is_enabled?: boolean }
export interface Student { id: string; name: string; login_identifier: string }
export type StudentStatus = "active" | "inactive";
export interface ManagedStudent {
  id: string;
  name: string;
  login_identifier: string;
  email: string | null;
  mobile: string | null;
  school_name: string | null;
  school_location: string | null;
  curriculum_id: string;
  board: BoardCode;
  state_code: string | null;
  class_level: number;
  status: StudentStatus;
  created_at: string;
  updated_at: string;
}
export interface StudentListResponse { items: ManagedStudent[]; total: number; limit: number; offset: number }
export interface StudentCredentials { student: ManagedStudent; temporary_password: string }
export interface ChangePasswordInput { current_password: string; new_password: string; confirm_password: string }

export interface Option { id: string; text: string }
export interface TeacherQuestion {
  id: string; text: string; type: QuestionType; marks: number;
  options?: Option[]; correct_option_id?: string | null; reference_answer: string;
  status: QuestionStatus; difficulty: string; style: string; chapter_title?: string;
  topic_title?: string | null; validation_flags?: string[];
}
export interface GenerationBatch {
  id: string; status: "queued" | "generating" | "completed" | "failed";
  failure_reason?: string | null; calculated_marks: number; questions: TeacherQuestion[];
  curriculum_id: string; subject_id: string; textbook_id: string; term_id: string; chapter_id: string; topic_id?: string | null;
  board?: BoardCode; state_code?: string | null; class_level?: number; subject_title?: string; textbook_title?: string; term_title?: string; chapter_title?: string; topic_title?: string | null;
  marks?: Record<string, number>;
}
export interface GenerationBatchSummary {
  id: string; status: GenerationBatch["status"]; calculated_marks: number;
  term_title: string; chapter_title: string; topic_title?: string | null;
  curriculum_id?: string; board?: BoardCode; state_code?: string | null; class_level?: number; subject_id?: string; subject_title?: string; textbook_id?: string; textbook_title?: string;
  failure_reason?: string | null; created_at: string;
}
export interface TestSummary { id?: string; test_id?: string; title: string; status?: string; total_marks?: number; published_at?: string; attempt_id?: string; attempt_status?: string; awarded_total?: number; max_total?: number; percentage?: number; board?: BoardCode; state_code?: string | null; class_level?: number; subject_title?: string }
export interface TeacherDashboard { total_tests: number; published_tests: number; submitted_attempts: number; pending_evaluation: number; recent_tests: TestSummary[] }
export interface StudentDashboard { available_tests: TestSummary[]; submitted_tests: TestSummary[]; completed_tests: TestSummary[] }

export interface StudentQuestion { id: string; order: number; text: string; type: QuestionType; marks: number; options?: Option[]; board_label?: string; class_level?: number; subject_label?: string; textbook_label?: string; term_label?: string; chapter_label?: string; topic_label?: string | null }
export interface AnswerImage { id: string; page_order: number; file_name?: string; preview_url: string; status?: string }
export interface StudentAnswer { id: string; test_question_id: string; answer_type: string; selected_option_id?: string | null; text_answer?: string | null; version: number; images?: AnswerImage[] }
export interface Attempt {
  id: string; test_id: string; test_title?: string; status: AttemptStatus; unanswered_count: number;
  short_answer_max_chars?: number; questions: StudentQuestion[]; answers: StudentAnswer[];
}
export interface TeacherAttempt { attempt_id: string; status: AttemptStatus; submitted_at?: string | null; test: {id:string;title:string;total_marks:number}; student:{id:string;name:string}; result?: {awarded_total:number;max_total:number;percentage:number;published_at:string}|null; questions: Array<{id:string;order:number;text:string;type:QuestionType;marks:number;options?:Option[];reference_answer:string;answer?:{id:string;answer_type:string;selected_option_id?:string|null;text_answer?:string|null;images?:AnswerImage[]}|null;evaluation?:{status:EvaluationStatus;awarded_marks:number;feedback?:string;version:number}|null}> }
export interface EvaluationQueueItem { attempt_id: string; test_id:string; test_title: string; student_name: string; submitted_at: string; status: AttemptStatus }
export interface TeacherHistoryItem { attempt_id: string; test_id: string; student_id: string; student_name: string; test_name: string; date: string; total_marks: number; obtained_marks: number | null; answered_count: number; unanswered_count: number; status: AttemptStatus; result_published: boolean }
export interface StudentHistoryItem { test_id: string; attempt_id: string | null; test_name: string; date: string; assigned_at: string; total_marks: number; obtained_marks: number | null; percentage: number | null; answered_count: number; unanswered_count: number; status: AttemptStatus | "assigned"; result_published: boolean; board: BoardCode; state_code: string | null; class_level: number; subject_title: string }
export interface TestAssignmentStudent { id: string; name: string; login_identifier: string; status: StudentStatus; assigned: boolean; attempt_id: string | null; attempt_status: AttemptStatus | null }
export interface TeacherTestSummary { id: string; title: string; status: "draft" | "published"; total_marks: number; published_at: string | null; created_at: string; board: BoardCode; state_code: string | null; class_level: number; subject_title: string; assigned_count: number; attempt_count: number }
export interface ResultDetail { attempt_id: string; test_title?: string; awarded_total: number; max_total: number; percentage: number; published_at: string; overall_comment?:string|null; questions: Array<{test_question_id: string; order: number; question_text: string; question_type: QuestionType; options?: Option[]; status: EvaluationStatus; awarded_marks: number; max_marks: number; feedback?: string; answer?: {selected_option_id?: string | null; text_answer?: string | null; images?: AnswerImage[]} | null}> }
