from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import pymupdf


QUESTION_START = re.compile(
    r"(?m)^\s*(?:Q(?:uestion)?\s*)?(\d{1,4})\s*[.)\-:]\s+"
)
OPTION_LINE = re.compile(r"(?m)^\s*[(\[]?[A-Da-d][)\].:]\s+")


@dataclass(frozen=True)
class PageExtraction:
    page_number: int
    text: str
    image_count: int
    block_count: int


@dataclass(frozen=True)
class ExtractedAsset:
    page_number: int
    asset_index: int
    xref: int
    mime_type: str
    extension: str
    data: bytes
    width: int
    height: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ExtractedContentBlock:
    page_number: int
    block_index: int
    kind: str
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ExtractedQuestion:
    number: str | None
    page_start: int
    page_end: int
    text: str


def extract_document(path: str) -> list[PageExtraction]:
    pages: list[PageExtraction] = []
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            blocks = page.get_text("blocks", sort=True)
            text = page.get_text("text", sort=True).strip()
            pages.append(
                PageExtraction(
                    page_number=index + 1,
                    text=text,
                    image_count=len(page.get_images(full=True)),
                    block_count=len(blocks),
                )
            )
    return pages


def extract_document_assets(path: str) -> list[ExtractedAsset]:
    assets: list[ExtractedAsset] = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            seen_xrefs: set[int] = set()
            asset_index = 0
            for image in page.get_images(full=True):
                xref = int(image[0])
                if xref <= 0 or xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    extracted = document.extract_image(xref)
                    rects = page.get_image_rects(xref)
                    bbox = tuple(float(v) for v in (rects[0] if rects else (0, 0, 0, 0)))
                except Exception:
                    continue
                data = extracted.get("image", b"")
                if not data:
                    continue
                asset_index += 1
                mime_type = str(extracted.get("ext", "bin")).lower()
                extension = mime_type if mime_type != "jpeg" else "jpg"
                assets.append(
                    ExtractedAsset(
                        page_number=page_number,
                        asset_index=asset_index,
                        xref=xref,
                        mime_type=f"image/{mime_type}" if "/" not in mime_type else mime_type,
                        extension=extension,
                        data=data,
                        width=int(extracted.get("width", 0) or 0),
                        height=int(extracted.get("height", 0) or 0),
                        bbox=bbox,
                    )
                )
    return assets


def asset_id(document_id: str, item: ExtractedAsset) -> str:
    digest = hashlib.sha256(item.data).hexdigest()[:20]
    return f"{document_id}-p{item.page_number}-a{item.asset_index}-{digest}"


def reconstruct_question_candidates(
    pages: list[PageExtraction],
) -> list[ExtractedQuestion]:
    candidates: list[ExtractedQuestion] = []
    current_number: str | None = None
    current_start: int | None = None
    current_lines: list[str] = []
    last_content_page: int | None = None

    def flush(end_page: int | None = None) -> None:
        nonlocal current_number, current_start, current_lines, last_content_page
        text = "\n".join(current_lines).strip()
        if current_start is not None and text:
            candidates.append(
                ExtractedQuestion(
                    number=current_number,
                    page_start=current_start,
                    page_end=end_page or last_content_page or current_start,
                    text=text,
                )
            )
        current_number = None
        current_start = None
        current_lines = []
        last_content_page = None

    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        for line in lines:
            match = QUESTION_START.match(line)
            if match:
                if current_start is not None:
                    flush(last_content_page)
                current_number = match.group(1)
                current_start = page.page_number
                current_lines = [line]
                last_content_page = page.page_number
            elif current_start is not None:
                current_lines.append(line)
                last_content_page = page.page_number

    if current_start is not None:
        flush(last_content_page)

    return [
        candidate
        for candidate in candidates
        if len(candidate.text) >= 12
        and (OPTION_LINE.search(candidate.text) or "?" in candidate.text)
    ]


def extract_content_blocks(path: str) -> list[ExtractedContentBlock]:
    blocks: list[ExtractedContentBlock] = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            raw_blocks = page.get_text("blocks", sort=True)
            next_index = 0
            for raw in raw_blocks:
                if len(raw) < 7 or int(raw[6] or 0) != 0:
                    continue
                raw_text = str(raw[4]).strip()
                if not raw_text:
                    continue

                lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                if not lines:
                    continue

                block_height = max(float(raw[3]) - float(raw[1]), 1.0)
                line_height = block_height / len(lines)
                for line_offset, text in enumerate(lines):
                    first_line = text
                    if QUESTION_START.match(first_line):
                        kind = "question"
                    elif OPTION_LINE.match(first_line):
                        kind = "option"
                    elif re.fullmatch(
                        r"(?:Figure|Fig\.?|Diagram|Table)\s*\d*.*",
                        first_line,
                        re.IGNORECASE,
                    ):
                        kind = "caption"
                    elif re.search(r"[=∫√^]", text) and len(text) <= 500:
                        kind = "equation"
                    elif (
                        len(first_line) <= 100
                        and not first_line.endswith((".", "?", ":", ";"))
                    ):
                        kind = "heading"
                    else:
                        kind = "paragraph"

                    y0 = float(raw[1]) + line_offset * line_height
                    y1 = float(raw[1]) + (line_offset + 1) * line_height
                    blocks.append(
                        ExtractedContentBlock(
                            page_number=page_number,
                            block_index=next_index,
                            kind=kind,
                            text=text,
                            bbox=(float(raw[0]), y0, float(raw[2]), y1),
                        )
                    )
                    next_index += 1
    return blocks
