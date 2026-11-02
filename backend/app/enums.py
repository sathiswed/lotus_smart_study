from enum import StrEnum


class Role(StrEnum):
    TEACHER = "teacher"
    STUDENT = "student"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class TermCode(StrEnum):
    TERM_1 = "term_1"
    TERM_2 = "term_2"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestionType(StrEnum):
    MCQ = "mcq"
    ONE_MARK = "one_mark"
    TWO_MARK = "two_mark"
    THREE_MARK = "three_mark"
    FIVE_MARK = "five_mark"
    CASE_STUDY = "case_study"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    MIXED = "mixed"


class QuestionStyle(StrEnum):
    STANDARD = "standard"
    CBSE_STYLE = "cbse_style"
    CHALLENGING = "challenging"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class TestStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EVALUATION_IN_PROGRESS = "evaluation_in_progress"
    EVALUATED = "evaluated"
    RESULT_PUBLISHED = "result_published"


class AnswerType(StrEnum):
    MCQ = "mcq"
    TEXT = "text"
    IMAGE = "image"


class ImageStatus(StrEnum):
    UPLOADING = "uploading"
    READY = "ready"
    FAILED = "failed"


class EvaluationStatus(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    PARTIAL = "partial"


class ResultStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
