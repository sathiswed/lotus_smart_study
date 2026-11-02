from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Chapter, Curriculum, SourceChunk, SourceDocument, Subject, Term, Textbook, Topic
from .contracts import GenerationScope, SourceExcerpt


class CurriculumScopeError(ValueError):
    pass


class SourceContentUnavailableError(LookupError):
    pass


@dataclass(slots=True)
class ExactScopeRetriever:
    """Retrieves only chunks in the selected verified curriculum ancestry."""

    session: AsyncSession
    maximum_chunks: int = 24

    async def resolve_scope(
        self, textbook_id: UUID, chapter_id: UUID, topic_id: UUID | None
    ) -> GenerationScope:
        row = (
            await self.session.execute(
                select(Curriculum, Subject, Textbook, Term, Chapter)
                .join(Subject, Subject.curriculum_id == Curriculum.id)
                .join(Textbook, Textbook.subject_id == Subject.id)
                .join(Chapter, Chapter.textbook_id == Textbook.id)
                .join(
                    Term,
                    (Term.id == Chapter.term_id)
                    & (Term.subject_id == Subject.id),
                )
                .where(Textbook.id == textbook_id, Chapter.id == chapter_id)
            )
        ).one_or_none()
        if row is None:
            raise CurriculumScopeError("Textbook and chapter ancestry is invalid")
        curriculum, subject, textbook, term, chapter = row
        if textbook.processing_status != "ready":
            raise SourceContentUnavailableError("The selected textbook has not completed extraction and indexing")
        topic = None
        if topic_id is not None:
            topic = await self.session.scalar(
                select(Topic).where(
                    Topic.id == topic_id,
                    Topic.chapter_id == chapter_id,
                    Topic.is_enabled.is_(True),
                )
            )
            if topic is None:
                raise CurriculumScopeError("Topic is not enabled for this chapter")
        scope = GenerationScope(
            curriculum_id=curriculum.id,
            board=curriculum.board,
            state_code=curriculum.state_code,
            class_level=curriculum.class_level,
            subject_id=subject.id,
            subject_code=subject.code,
            subject_title=subject.title,
            textbook_id=textbook.id,
            textbook_title=textbook.title,
            term_id=term.id,
            term_title=term.title,
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            topic_id=topic.id if topic else None,
            topic_title=topic.title if topic else None,
        )
        available = await self.session.scalar(
            select(func.count())
            .select_from(SourceChunk)
            .join(SourceDocument, SourceDocument.id == SourceChunk.source_document_id)
            .where(
                SourceChunk.textbook_id == textbook.id,
                SourceChunk.term_id == term.id,
                SourceChunk.chapter_id == chapter.id,
                SourceDocument.textbook_id == textbook.id,
                SourceDocument.term_id == term.id,
                SourceDocument.chapter_id == chapter.id,
                SourceDocument.ingestion_status == "ready",
            )
        )
        if not available:
            raise SourceContentUnavailableError("No indexed textbook content exists for the selected chapter")
        return scope

    async def retrieve(
        self, scope: GenerationScope, search_text: str | None = None
    ) -> list[SourceExcerpt]:
        filters = [
            SourceChunk.textbook_id == scope.textbook_id,
            SourceChunk.term_id == scope.term_id,
            SourceChunk.chapter_id == scope.chapter_id,
        ]
        if scope.topic_id is not None:
            filters.append(SourceChunk.topic_id == scope.topic_id)

        # Ranking is applied only after mandatory exact ancestry filters.
        rank = literal(0.0)
        if search_text:
            rank = func.ts_rank_cd(
                func.to_tsvector("english", SourceChunk.content),
                func.plainto_tsquery("english", search_text),
            )
        rows = (
            await self.session.scalars(
                select(SourceChunk)
                .join(
                    SourceDocument,
                    SourceDocument.id == SourceChunk.source_document_id,
                )
                .where(*filters)
                .where(
                    SourceDocument.textbook_id == scope.textbook_id,
                    SourceDocument.term_id == scope.term_id,
                    SourceDocument.chapter_id == scope.chapter_id,
                    SourceDocument.ingestion_status == "ready",
                )
                .order_by(rank.desc(), SourceChunk.sequence.asc())
                .limit(self.maximum_chunks)
            )
        ).all()
        excerpts = [
            SourceExcerpt(
                chunk_id=row.id,
                document_id=row.source_document_id,
                textbook_id=row.textbook_id,
                term_id=row.term_id,
                chapter_id=row.chapter_id,
                topic_id=row.topic_id,
                page_start=row.page_start,
                page_end=row.page_end,
                content=row.content,
            )
            for row in rows
        ]
        if not excerpts:
            raise SourceContentUnavailableError(
                "No indexed textbook content exists for the selected exact scope"
            )
        self._assert_exact_scope(excerpts, scope)
        return excerpts

    @staticmethod
    def _assert_exact_scope(
        excerpts: list[SourceExcerpt], scope: GenerationScope
    ) -> None:
        for excerpt in excerpts:
            if excerpt.textbook_id != scope.textbook_id or excerpt.term_id != scope.term_id or excerpt.chapter_id != scope.chapter_id:
                raise CurriculumScopeError("Retrieved content escaped selected scope")
            if scope.topic_id is not None and excerpt.topic_id != scope.topic_id:
                raise CurriculumScopeError("Retrieved content escaped selected topic")
