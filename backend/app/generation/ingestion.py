from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID, uuid5

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Chapter, Curriculum, SourceChunk, SourceDocument, Subject, Term, Textbook, Topic
from .taxonomy import CLASS_8_CHAPTERS, ChapterDefinition


INGESTION_NAMESPACE = UUID("ec4e967f-5368-46fe-8622-3c30ca10305d")
MAX_CHUNK_CHARACTERS = 5000
CBSE_8_CURRICULUM_ID = UUID("10000000-0000-4000-8000-000000000001")
CBSE_8_MATH_SUBJECT_ID = UUID("10000000-0000-4000-8000-000000000002")
GANITA_PRAKASH_ID = UUID("10000000-0000-4000-8000-000000000003")


@dataclass(frozen=True, slots=True)
class ExtractedChunk:
    id: UUID
    document_id: UUID
    term_id: UUID
    chapter_id: UUID
    topic_id: UUID | None
    page_start: int
    page_end: int
    sequence: int
    content: str
    checksum: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    id: UUID
    term_id: UUID
    chapter_id: UUID
    source_path: str
    checksum: str
    version: str
    chunks: tuple[ExtractedChunk, ...]


@dataclass(frozen=True, slots=True)
class DetectedChapter:
    code: str
    title: str
    page_start: int
    page_end: int
    confidence: str


_EXPLICIT_CHAPTER = re.compile(
    r"^\s*(?:chapter|unit)\s*[-:]?\s*(\d{1,3}|[ivxlcdm]{1,8})"
    r"\s*(?:[-:–—]\s*)?(.*?)\s*$",
    re.IGNORECASE,
)
_SECTION_HEADING = re.compile(r"^\s*(\d{1,3})\.(\d{1,3})\s+(.{2,160}?)\s*$")
_TITLE_WITH_TRAILING_NUMBER = re.compile(r"^\s*(.{3,140}?[A-Za-z)])\s*(\d{1,3})\s*$")


def extract_pdf_pages(pdf_data: bytes) -> list[str]:
    """Extract readable page text once for detection and approved indexing."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ValueError("Textbook PDF text extraction failed") from exc
    if not pages or not any(pages):
        raise ValueError("Textbook PDF does not contain extractable text")
    return pages


def detect_pdf_chapters(pages: list[str]) -> list[DetectedChapter]:
    """Detect chapter boundaries from extracted PDF content, never filenames."""
    explicit_starts: dict[str, int] = {}
    section_starts: dict[str, int] = {}
    explicit_titles: dict[str, str] = {}
    trailing_titles: dict[str, tuple[int, str]] = {}

    for page_number, page_text in enumerate(pages, 1):
        lines = _clean_lines(page_text)
        for line_index, line in enumerate(lines):
            explicit = _EXPLICIT_CHAPTER.match(line)
            # A real chapter opener is page-heading material. Restricting this
            # signal to the top of a page avoids body references such as
            # "Chapter 2" becoming a false boundary near the end of a PDF.
            if explicit and line_index < 12:
                code = _chapter_code(explicit.group(1))
                if code:
                    explicit_starts.setdefault(code, page_number)
                    title = _clean_detected_title(explicit.group(2))
                    if not title:
                        for following in lines[line_index + 1 : line_index + 4]:
                            if _SECTION_HEADING.match(following):
                                break
                            title = _clean_detected_title(following)
                            if title:
                                break
                    if title:
                        explicit_titles.setdefault(code, title)
            section = _SECTION_HEADING.match(line)
            # Only x.1 can identify the beginning of chapter x. Later numbered
            # sections and examples must not create chapter records.
            if section and line_index < 14 and int(section.group(2)) == 1:
                code = str(int(section.group(1)))
                section_starts.setdefault(code, page_number)
            trailing = _TITLE_WITH_TRAILING_NUMBER.match(line)
            if line_index < 10 and trailing and _looks_like_title(trailing.group(1)):
                code = str(int(trailing.group(2)))
                trailing_titles.setdefault(code, (page_number, _clean_detected_title(trailing.group(1))))

    # A title followed by a number is often a running header. Treat it only as
    # supporting evidence for an explicit chapter marker or its first section;
    # it is never sufficient to create a boundary by itself.
    starts: dict[str, int] = dict(section_starts)
    for code, page_number in explicit_starts.items():
        starts[code] = min(starts.get(code, page_number), page_number)
    for code, (_, title) in trailing_titles.items():
        if code in starts and title:
            explicit_titles.setdefault(code, title)

    if not starts:
        return []

    ordered = sorted(starts.items(), key=lambda item: (item[1], _chapter_sort_key(item[0])))
    detected: list[DetectedChapter] = []
    for index, (code, detected_start) in enumerate(ordered):
        # Chapter-only PDFs often begin with introductory content before the
        # first numbered section. Include it when the first marker is near the start.
        page_start = 1 if index == 0 and detected_start <= 3 else detected_start
        page_end = ordered[index + 1][1] - 1 if index + 1 < len(ordered) else len(pages)
        if page_end < page_start:
            continue
        title = explicit_titles.get(code) or _infer_running_title(
            pages[page_start - 1 : page_end], code
        )
        detected.append(
            DetectedChapter(
                code=code,
                title=title,
                page_start=page_start,
                page_end=page_end,
                confidence="high" if code in explicit_titles and title else "medium" if title else "low",
            )
        )
    return detected


def build_page_chunks(
    pages: list[str], page_start: int, page_end: int
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    sequence = 0
    for page_number in range(page_start, page_end + 1):
        page_text = pages[page_number - 1].strip()
        for piece in _split_text(page_text, MAX_CHUNK_CHARACTERS):
            content = piece.strip()
            if not content:
                continue
            sequence += 1
            chunks.append(
                {
                    "page_start": page_number,
                    "page_end": page_number,
                    "sequence": sequence,
                    "content": content,
                    "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                }
            )
    return chunks


def _clean_lines(page_text: str) -> list[str]:
    return [" ".join(line.split()) for line in page_text.splitlines() if line.strip()]


def _chapter_code(raw: str) -> str | None:
    value = raw.strip().casefold()
    if value.isdigit():
        return str(int(value))
    roman_values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = previous = 0
    for character in reversed(value):
        current = roman_values.get(character)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return str(total) if total > 0 else None


def _clean_detected_title(value: str) -> str:
    value = re.sub(r"^[\s\-:\u2013\u2014|.]+|[\s\-:\u2013\u2014|.]+$", "", value)
    title = " ".join(value.strip(" -:–—|.").split())
    return title[:255] if _looks_like_title(title) else ""


def _looks_like_title(value: str) -> bool:
    title = " ".join(value.split())
    words = title.split()
    if not 1 <= len(words) <= 16 or len(title) > 140:
        return False
    if title.endswith(("?", ";")) or title.count(".") > 1:
        return False
    if sum(character.isalpha() for character in title) < max(3, len(title) // 3):
        return False
    lowered = title.casefold()
    if lowered in {"chapter", "unit", "part", "section"}:
        return False
    return not any(marker in lowered for marker in ("ganita prakash", "grade ", "contents", "exercise"))


def _infer_running_title(chapter_pages: list[str], code: str) -> str:
    candidates: dict[str, tuple[str, int]] = {}
    for page_text in chapter_pages:
        for line in _clean_lines(page_text)[:6]:
            if line.isdigit() or _SECTION_HEADING.match(line) or _EXPLICIT_CHAPTER.match(line):
                continue
            cleaned = _clean_detected_title(line)
            if not cleaned:
                continue
            normalized = cleaned.casefold()
            current = candidates.get(normalized)
            candidates[normalized] = (cleaned, (current[1] if current else 0) + 1)
    if not candidates:
        return ""
    # Repeated running headers are more reliable than body sentences. For a
    # single occurrence, prefer a concise title-cased line.
    ranked = sorted(
        candidates.values(),
        key=lambda item: (item[1], item[0].istitle(), -len(item[0])),
        reverse=True,
    )
    best, count = ranked[0]
    return best if count > 1 or best.istitle() else ""


def _chapter_sort_key(code: str) -> tuple[int, str]:
    return (int(code), code) if code.isdigit() else (10_000, code)


def stable_id(*parts: str) -> UUID:
    return uuid5(INGESTION_NAMESPACE, ":".join(parts))


def approved_catalog() -> dict[str, object]:
    terms: list[dict[str, object]] = []
    chapters: list[dict[str, object]] = []
    topics: list[dict[str, object]] = []
    for term_sequence, term_code in enumerate(("term_1", "term_2"), 1):
        term_id = stable_id("term", term_code)
        terms.append({"id": term_id, "subject_id": CBSE_8_MATH_SUBJECT_ID, "code": term_code, "title": f"Term {term_sequence}", "sequence": term_sequence})
        for chapter_sequence, chapter in enumerate(
            (item for item in CLASS_8_CHAPTERS if item.term_code == term_code), 1
        ):
            chapter_id = stable_id("chapter", term_code, chapter.code)
            chapters.append({
                "id": chapter_id, "textbook_id": GANITA_PRAKASH_ID, "term_id": term_id, "code": chapter.code,
                "title": chapter.title, "sequence": chapter_sequence,
            })
            for topic_sequence, topic in enumerate(chapter.topics, 1):
                topics.append({
                    "id": stable_id("topic", term_code, chapter.code, topic.code),
                    "chapter_id": chapter_id, "section_code": topic.code,
                    "title": topic.title, "sequence": topic_sequence, "is_enabled": True,
                })
    return {
        "curricula": [{"id": CBSE_8_CURRICULUM_ID, "code": "cbse-8", "board": "cbse", "state_code": None, "class_level": 8}],
        "subjects": [{"id": CBSE_8_MATH_SUBJECT_ID, "curriculum_id": CBSE_8_CURRICULUM_ID, "code": "mathematics", "title": "Mathematics"}],
        "textbooks": [{"id": GANITA_PRAKASH_ID, "subject_id": CBSE_8_MATH_SUBJECT_ID, "title": "Ganita Prakash", "edition": "existing-pilot", "processing_status": "ready"}],
        "terms": terms, "chapters": chapters, "topics": topics,
    }


def extract_textbooks(source_root: Path) -> list[ExtractedDocument]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for textbook ingestion") from exc

    documents: list[ExtractedDocument] = []
    for chapter in CLASS_8_CHAPTERS:
        term_dir = "Term1" if chapter.term_code == "term_1" else "Term2"
        path = source_root / "class-8" / term_dir / chapter.pdf_name
        if not path.is_file():
            raise FileNotFoundError(f"Required approved textbook is missing: {path}")
        raw = path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        term_id = stable_id("term", chapter.term_code)
        chapter_id = stable_id("chapter", chapter.term_code, chapter.code)
        document_id = stable_id("document", chapter.term_code, chapter.code, checksum)
        reader = PdfReader(str(path))
        chunks = _extract_chapter_chunks(reader.pages, chapter, document_id, term_id, chapter_id)
        if not chunks:
            raise ValueError(f"No readable text extracted from {path}")
        extracted_topic_ids = {chunk.topic_id for chunk in chunks if chunk.topic_id}
        missing_topics = [
            topic.code
            for topic in chapter.topics
            if stable_id("topic", chapter.term_code, chapter.code, topic.code)
            not in extracted_topic_ids
        ]
        if missing_topics:
            raise ValueError(
                f"Approved topics have no extracted content in {path}: "
                + ", ".join(missing_topics)
            )
        documents.append(ExtractedDocument(
            id=document_id, term_id=term_id, chapter_id=chapter_id,
            source_path=path.as_posix(), checksum=checksum, version=checksum[:16],
            chunks=tuple(chunks),
        ))
    return documents


def _extract_chapter_chunks(
    pages: Iterable[object], chapter: ChapterDefinition, document_id: UUID,
    term_id: UUID, chapter_id: UUID,
) -> list[ExtractedChunk]:
    topic_by_code = {topic.code: topic for topic in chapter.topics}
    topic_pattern = re.compile(
        r"(?m)^\s*(" + "|".join(re.escape(code) for code in topic_by_code) + r")\s+"
    )
    active_topic_code: str | None = None
    chunks: list[ExtractedChunk] = []
    sequence = 0
    for page_number, page in enumerate(pages, 1):
        page_text = (page.extract_text() or "").strip()
        if not page_text:
            continue
        parts = topic_pattern.split(page_text)
        segments: list[tuple[str | None, str]] = []
        if len(parts) == 1:
            segments.append((active_topic_code, page_text))
        else:
            if parts[0].strip():
                segments.append((active_topic_code, parts[0].strip()))
            for index in range(1, len(parts), 2):
                active_topic_code = parts[index]
                body = parts[index + 1] if index + 1 < len(parts) else ""
                segments.append((active_topic_code, f"{active_topic_code} {body}".strip()))
        for topic_code, segment in segments:
            for piece in _split_text(segment, MAX_CHUNK_CHARACTERS):
                if not piece.strip():
                    continue
                sequence += 1
                topic_id = (
                    stable_id("topic", chapter.term_code, chapter.code, topic_code)
                    if topic_code else None
                )
                chunk_checksum = hashlib.sha256(piece.encode("utf-8")).hexdigest()
                chunks.append(ExtractedChunk(
                    id=stable_id("chunk", str(document_id), str(sequence), chunk_checksum),
                    document_id=document_id, term_id=term_id, chapter_id=chapter_id,
                    topic_id=topic_id, page_start=page_number, page_end=page_number,
                    sequence=sequence, content=piece, checksum=chunk_checksum,
                ))
    return chunks


def _split_text(text_value: str, maximum: int) -> list[str]:
    if len(text_value) <= maximum:
        return [text_value]
    paragraphs = re.split(r"\n\s*\n", text_value)
    output: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > maximum:
            output.append(current)
            current = paragraph
        else:
            current = candidate
        while len(current) > maximum:
            output.append(current[:maximum])
            current = current[maximum:]
    if current:
        output.append(current)
    return output


async def ingest_into_database(session: AsyncSession, source_root: Path) -> dict[str, int]:
    catalog = approved_catalog()
    documents = extract_textbooks(source_root)
    curriculum = await session.get(Curriculum, CBSE_8_CURRICULUM_ID)
    if curriculum is None:
        session.add(Curriculum(**catalog["curricula"][0]))
    subject = await session.get(Subject, CBSE_8_MATH_SUBJECT_ID)
    if subject is None:
        session.add(Subject(**catalog["subjects"][0]))
    textbook = await session.get(Textbook, GANITA_PRAKASH_ID)
    if textbook is None:
        session.add(Textbook(**catalog["textbooks"][0]))
    else:
        textbook.processing_status = "ready"
        textbook.failure_reason = None
    await session.flush()
    for term in catalog["terms"]:
        record = await session.get(Term, term["id"])
        if record is None:
            record = Term(id=term["id"], subject_id=term["subject_id"], code=term["code"], title=term["title"], sequence=term["sequence"])
            session.add(record)
        else:
            record.subject_id, record.code = term["subject_id"], term["code"]
            record.title, record.sequence = term["title"], term["sequence"]
    for chapter in catalog["chapters"]:
        record = await session.get(Chapter, chapter["id"])
        if record is None:
            record = Chapter(**chapter)
            session.add(record)
        else:
            record.textbook_id, record.term_id = chapter["textbook_id"], chapter["term_id"]
            record.title, record.sequence = chapter["title"], chapter["sequence"]
    for topic in catalog["topics"]:
        record = await session.get(Topic, topic["id"])
        if record is None:
            record = Topic(**topic)
            session.add(record)
        else:
            record.title, record.sequence, record.is_enabled = topic["title"], topic["sequence"], True
    await session.flush()
    approved_chapter_ids = [chapter["id"] for chapter in catalog["chapters"]]
    # Preserve historical source records for traceability, but retire them
    # from retrieval before marking this complete ingestion pass as current.
    await session.execute(
        update(SourceDocument)
        .where(SourceDocument.textbook_id == GANITA_PRAKASH_ID, SourceDocument.chapter_id.in_(approved_chapter_ids))
        .values(ingestion_status="retired")
    )
    chunk_count = 0
    for document in documents:
        source_record = await session.get(SourceDocument, document.id)
        metadata = {"board": "cbse", "class_level": 8, "subject": "mathematics", "textbook_id": str(GANITA_PRAKASH_ID), "authoritative_pattern_corpus": False}
        if source_record is None:
            source_record = SourceDocument(
                id=document.id, textbook_id=GANITA_PRAKASH_ID, term_id=document.term_id, chapter_id=document.chapter_id,
                topic_id=None, path=document.source_path, checksum=document.checksum,
                version=document.version, ingestion_status="ready", document_metadata=metadata,
            )
            session.add(source_record)
        else:
            source_record.textbook_id = GANITA_PRAKASH_ID
            source_record.path = document.source_path
            source_record.checksum = document.checksum
            source_record.version = document.version
            source_record.ingestion_status = "ready"
            source_record.document_metadata = metadata
        await session.flush()
        await session.execute(delete(SourceChunk).where(SourceChunk.source_document_id == document.id))
        for chunk in document.chunks:
            session.add(SourceChunk(
                id=chunk.id, source_document_id=chunk.document_id, textbook_id=GANITA_PRAKASH_ID, term_id=chunk.term_id,
                chapter_id=chunk.chapter_id, topic_id=chunk.topic_id,
                page_start=chunk.page_start, page_end=chunk.page_end,
                sequence=chunk.sequence, content=chunk.content,
                checksum=chunk.checksum, index_reference=None,
            ))
            chunk_count += 1
    await session.commit()
    return {"terms": 2, "chapters": len(CLASS_8_CHAPTERS), "documents": len(documents), "chunks": chunk_count}


def write_manifest(source_root: Path, output_path: Path) -> None:
    documents = extract_textbooks(source_root)
    payload = {
        "catalog": approved_catalog(),
        "documents": [asdict(document) for document in documents],
        "authoritative_cbse_corpus_used": False,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
