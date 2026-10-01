from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf


QUESTION_START = re.compile(
    r"(?m)^\\s*(?:Q(?:uestion)?\\s*)?(\\d{1,4})\\s*[.)\\-:]\\s+"
)
OPTION_LINE = re.compile(r"(?m)^\\s*[(\\[]?[A-Da-d][)\\].:]\\s+")


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

    def flush(end_page: int) -> None:
        nonlocal current_number, current_start, current_lines
        text = "\\n".join(current_lines).strip()
        if current_start is not None and text:
            candidates.append(
                ExtractedQuestion(
                    number=current_number,
                    page_start=current_start,
                    page_end=end_page,
                    text=text,
                )
            )
        current_number = None
        current_start = None
        current_lines = []

    for page in pages:
        lines = page.text.splitlines()
        for line in lines:
            match = QUESTION_START.match(line)
            if match:
                if current_start is not None:
                    flush(page.page_number)
                current_number = match.group(1)
                current_start = page.page_number
                current_lines = [line.strip()]
            elif current_start is not None:
                current_lines.append(line.rstrip())

        if current_start is not None:
            current_lines.append("")

    if current_start is not None:
        flush(pages[-1].page_number if pages else current_start)

    return [
        candidate
        for candidate in candidates
        if len(candidate.text) >= 12
        and (OPTION_LINE.search(candidate.text) or "?" in candidate.text)
    ]
