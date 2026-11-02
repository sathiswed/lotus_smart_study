import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import AnswerType, AttemptStatus, EvaluationStatus, Role, TestStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: uuid.UUID
    name: str
    login_identifier: str
    role: Role
    must_change_password: bool


class LoginIn(BaseModel):
    login_identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)
    confirm_password: str = Field(min_length=10, max_length=256)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if any(character.isspace() for character in value):
            raise ValueError("New password must not contain whitespace")
        if re.search(r"[a-z]", value) is None:
            raise ValueError("New password must contain a lowercase letter")
        if re.search(r"[A-Z]", value) is None:
            raise ValueError("New password must contain an uppercase letter")
        if re.search(r"[0-9]", value) is None:
            raise ValueError("New password must contain a number")
        if re.search(r"[^A-Za-z0-9\s]", value) is None:
            raise ValueError("New password must contain a symbol")
        return value

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from the current password")
        return self


class AnswerSaveIn(BaseModel):
    answer_type: AnswerType
    selected_option_id: str | None = None
    text_answer: str | None = None
    version: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_value(self):
        if self.answer_type == AnswerType.MCQ and (self.selected_option_id is None or self.text_answer is not None):
            raise ValueError("MCQ answers require only selected_option_id")
        if self.answer_type == AnswerType.TEXT and (self.text_answer is None or self.selected_option_id is not None):
            raise ValueError("Text answers require only text_answer")
        if self.answer_type == AnswerType.IMAGE and (self.selected_option_id is not None or self.text_answer is not None):
            raise ValueError("Image answers do not accept selected_option_id or text_answer")
        return self


class EvaluationSaveIn(BaseModel):
    status: EvaluationStatus
    awarded_marks: Decimal = Field(ge=0)
    feedback: str | None = Field(default=None, max_length=4000)
    version: int = Field(ge=0)


class UploadUrlIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str
    byte_size: int = Field(gt=0)


class CompleteUploadIn(BaseModel):
    checksum: str | None = Field(default=None, max_length=64)


class ImageOrderIn(BaseModel):
    image_ids: list[uuid.UUID]


class StudentQuestionOut(BaseModel):
    id: uuid.UUID
    order: int
    text: str
    type: str
    marks: int
    options: list[Any] | None
    term_label: str
    chapter_label: str
    topic_label: str | None


class AttemptSummaryOut(BaseModel):
    id: uuid.UUID
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    unanswered_count: int


class TestSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    total_marks: int
    status: TestStatus
