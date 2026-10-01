from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pymupdf

from .classifier import DEFAULT_CLASSIFIER, QuestionClassifier
from .extractor import (
    asset_id,
    extract_document,
    extract_document_assets,
    extract_content_blocks,
    reconstruct_question_candidates,
)
from .question_intelligence import HybridQuestionIntelligence
from .solution_engine import SolutionEngine
from .models import (
    ClassificationStatus,
    DocumentAsset,
    ContentBlock,
    DocumentRecord,
    ProcessingJob,
    ProcessingStatus,
    Provenance,
    QuestionCandidate,
    TaxonomyProposal,
    TaxonomyProposalResolution,
    TaxonomyProposalStatus,
    Solution,
    LibraryItem,
)
from .store import KnowledgeStore
from .taxonomy import DEFAULT_TAXONOMY, Taxonomy
from .taxonomy_registry import TaxonomyRegistry
from .taxonomy_ai import (
    TaxonomyProposalEngine,
    TaxonomyProposalProvider,
)


class KnowledgeService:
    def __init__(
        self,
        store: KnowledgeStore,
        storage_dir: str | Path,
        taxonomy: Taxonomy = DEFAULT_TAXONOMY,
        classifier: QuestionClassifier = DEFAULT_CLASSIFIER,
        taxonomy_proposal_provider: TaxonomyProposalProvider | None = None,
        question_intelligence: HybridQuestionIntelligence | None = None,
        solution_engine: SolutionEngine | None = None,
    ) -> None:
        self.store = store
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.registry = TaxonomyRegistry(store)
        self.taxonomy = self.registry.taxonomy if taxonomy is DEFAULT_TAXONOMY else taxonomy
        self.classifier = classifier
        self.taxonomy_proposal_provider = taxonomy_proposal_provider
        self.question_intelligence = question_intelligence
        self.solution_engine = solution_engine

    def ingest_pdf(self, filename: str, content: bytes) -> DocumentRecord:
        if not content:
            raise ValueError("PDF content is empty")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF documents are supported in this phase")

        digest = hashlib.sha256(content).hexdigest()
        document_id = digest[:24]
        source_path = self.storage_dir / f"{document_id}.pdf"
        source_path.write_bytes(content)

        try:
            with pymupdf.open(stream=content, filetype="pdf") as document:
                page_count = len(document)
        except Exception as exc:
            source_path.unlink(missing_ok=True)
            raise ValueError("The uploaded file is not a readable PDF") from exc

        if page_count == 0:
            source_path.unlink(missing_ok=True)
            raise ValueError("The uploaded PDF contains no pages")

        record = DocumentRecord(
            id=document_id,
            filename=filename,
            sha256=digest,
            page_count=page_count,
            status=ProcessingStatus.QUEUED,
        )
        self.store.save_document(record)

        job = ProcessingJob(
            id=str(uuid.uuid4()),
            document_id=document_id,
            status=ProcessingStatus.QUEUED,
            updated_at=self.store.now(),
        )
        self.store.save_job(job)
        return self.process_document(job.id)

    @staticmethod
    def _boxes_related(
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
        margin: float = 36.0,
    ) -> bool:
        ax0, ay0, ax1, ay1 = first
        bx0, by0, bx1, by1 = second
        return not (
            ax1 + margin < bx0
            or bx1 + margin < ax0
            or ay1 + margin < by0
            or by1 + margin < ay0
        )

    @staticmethod
    def _question_asset_ids(
        question_text: str,
        page_start: int,
        page_end: int,
        assets: list[DocumentAsset],
        content_blocks: list[ContentBlock],
    ) -> list[str]:
        """Associate only assets linked to text blocks that belong to the question.

        Fall back to page-range assets only when no matching block-level association
        exists, preserving compatibility with PDFs whose layout cannot be mapped.
        """
        normalized_question = " ".join(question_text.split()).casefold()
        block_asset_ids: list[str] = []
        for block in content_blocks:
            if not (page_start <= block.page_number <= page_end):
                continue
            if not block.asset_ids:
                continue
            normalized_block = " ".join(block.text.split()).casefold()
            if normalized_block and normalized_block in normalized_question:
                block_asset_ids.extend(block.asset_ids)

        if block_asset_ids:
            return list(dict.fromkeys(block_asset_ids))

        return list(dict.fromkeys(
            asset.id
            for asset in assets
            if page_start <= asset.page_number <= page_end
        ))

    def _build_question_records(
        self,
        document: DocumentRecord,
        pages,
        assets: list[DocumentAsset],
        content_blocks: list[ContentBlock],
    ) -> list[QuestionCandidate]:
        extracted = reconstruct_question_candidates(pages)
        questions: list[QuestionCandidate] = []
        for index, item in enumerate(extracted):
            question = QuestionCandidate(
                id=f"{document.id}-{index + 1}",
                document_id=document.id,
                page_start=item.page_start,
                page_end=item.page_end,
                text=item.text,
                number=item.number,
                asset_ids=self._question_asset_ids(
                    item.text,
                    item.page_start,
                    item.page_end,
                    assets,
                    content_blocks,
                ),
                provenance=[
                    Provenance(
                        document_id=document.id,
                        page_number=page,
                        source_hash=document.sha256,
                        extractor="pymupdf-text-v1",
                    )
                    for page in range(item.page_start, item.page_end + 1)
                ],
            )
            if self.question_intelligence is not None:
                question = self.question_intelligence.analyze(question)
            result = self.classifier.classify(question, self.taxonomy)
            questions.append(
                question.model_copy(
                    update={
                        "taxonomy_node_id": result.taxonomy_node_id,
                        "classification_status": (
                            ClassificationStatus.QUARANTINED
                            if result.quarantined
                            else ClassificationStatus.CLASSIFIED
                        ),
                        "classification_confidence": result.confidence,
                        "classification_reason": result.reason,
                    }
                )
            )
        return questions

    def process_document(self, job_id: str) -> DocumentRecord:
        job = self.store.get_job(job_id)
        if job is None:
            raise KeyError(job_id)

        record = self.store.get_document(job.document_id)
        if record is None:
            raise KeyError(job.document_id)

        source_path = self.storage_dir / f"{record.id}.pdf"
        if not source_path.is_file():
            failed = record.model_copy(
                update={"status": ProcessingStatus.FAILED, "error": "Source PDF is missing"}
            )
            self.store.save_document(failed)
            self.store.save_job(
                job.model_copy(
                    update={"status": ProcessingStatus.FAILED, "updated_at": self.store.now()}
                )
            )
            return failed

        running_job = job.model_copy(
            update={"status": ProcessingStatus.EXTRACTING, "updated_at": self.store.now()}
        )
        self.store.save_job(running_job)
        running = record.model_copy(
            update={"status": ProcessingStatus.EXTRACTING, "error": None}
        )
        self.store.save_document(running)

        try:
            actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if actual_hash != record.sha256:
                raise ValueError("Source PDF hash does not match recorded provenance")

            pages = extract_document(str(source_path))
            if len(pages) != record.page_count:
                raise ValueError("Source PDF page count does not match recorded metadata")

            extracted_assets = extract_document_assets(str(source_path))
            asset_root = self.storage_dir / "assets" / record.id
            asset_root.mkdir(parents=True, exist_ok=True)
            assets: list[DocumentAsset] = []
            for item in extracted_assets:
                current_id = asset_id(record.id, item)
                filename = f"{current_id}.{item.extension}"
                target = asset_root / filename
                target.write_bytes(item.data)
                assets.append(
                    DocumentAsset(
                        id=current_id,
                        document_id=record.id,
                        page_number=item.page_number,
                        asset_index=item.asset_index,
                        mime_type=item.mime_type,
                        sha256=hashlib.sha256(item.data).hexdigest(),
                        byte_size=len(item.data),
                        width=item.width,
                        height=item.height,
                        x0=item.bbox[0], y0=item.bbox[1], x1=item.bbox[2], y1=item.bbox[3],
                        xref=item.xref,
                        source_hash=record.sha256,
                        storage_path=str(target.relative_to(self.storage_dir)),
                    )
                )
            self.store.replace_document_assets(record.id, assets)

            extracted_blocks = extract_content_blocks(str(source_path))
            content_blocks: list[ContentBlock] = []
            assets_by_page: dict[int, list[str]] = {}
            for asset in assets:
                assets_by_page.setdefault(asset.page_number, []).append(asset.id)
            for block in extracted_blocks:
                block_id = f"{record.id}-p{block.page_number}-b{block.block_index}"
                linked_assets = [
                    asset.id
                    for asset in assets
                    if asset.page_number == block.page_number
                    and self._boxes_related(
                        (block.bbox[0], block.bbox[1], block.bbox[2], block.bbox[3]),
                        (asset.x0, asset.y0, asset.x1, asset.y1),
                    )
                ]
                content_blocks.append(
                    ContentBlock(
                        id=block_id,
                        document_id=record.id,
                        page_number=block.page_number,
                        block_index=block.block_index,
                        kind=block.kind,
                        text=block.text,
                        x0=block.bbox[0], y0=block.bbox[1],
                        x1=block.bbox[2], y1=block.bbox[3],
                        asset_ids=linked_assets,
                        source_hash=record.sha256,
                        extractor="pymupdf-content-blocks-v1",
                    )
                )
            self.store.replace_content_blocks(record.id, content_blocks)

            questions = self._build_question_records(
                record,
                pages,
                assets,
                content_blocks,
            )
            self.store.replace_questions(record.id, questions)

            ready = running.model_copy(
                update={
                    "status": ProcessingStatus.READY,
                    "question_count": len(questions),
                }
            )
            self.store.save_document(ready)
            now = self.store.now()
            existing_library = self.store.get_library_item(record.id)
            self.store.save_library_item(
                LibraryItem(
                    id=existing_library.id if existing_library else f"library-{record.id}",
                    document_id=record.id,
                    title=existing_library.title if existing_library else record.filename,
                    pinned=existing_library.pinned if existing_library else False,
                    archived=False,
                    fast_mode_enabled=existing_library.fast_mode_enabled if existing_library else True,
                    created_at=existing_library.created_at if existing_library else now,
                    updated_at=now,
                )
            )
            self.store.save_job(
                running_job.model_copy(
                    update={"status": ProcessingStatus.READY, "updated_at": self.store.now()}
                )
            )
            return ready
        except Exception as exc:
            failed = running.model_copy(
                update={"status": ProcessingStatus.FAILED, "error": str(exc)}
            )
            self.store.save_document(failed)
            self.store.save_job(
                running_job.model_copy(
                    update={"status": ProcessingStatus.FAILED, "updated_at": self.store.now()}
                )
            )
            raise


    def generate_solution(self, question_id: str) -> Solution:
        if self.solution_engine is None:
            raise RuntimeError("Solution engine is not configured")

        question = self.store.get_question(question_id)
        if question is None:
            raise KeyError(question_id)

        document = self.store.get_document(question.document_id)
        if document is None:
            raise KeyError(question.document_id)

        source_path = self.storage_dir / f"{document.id}.pdf"
        if not source_path.is_file():
            raise FileNotFoundError(document.id)

        actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual_hash != document.sha256:
            raise ValueError("Source PDF hash does not match recorded provenance")

        pages = extract_document(str(source_path))
        if len(pages) != document.page_count:
            raise ValueError("Source PDF page count does not match recorded metadata")

        source_pages = {
            page.page_number: page.text
            for page in pages
            if question.page_start <= page.page_number <= question.page_end
        }
        if not source_pages:
            raise ValueError("No source pages are available for this question")

        solution = self.solution_engine.generate(question, source_pages)
        self.store.save_solution(solution)
        return solution

    def get_solution(self, question_id: str) -> Solution | None:
        return self.store.get_solution(question_id)

    def resume_pending(self) -> list[DocumentRecord]:
        results: list[DocumentRecord] = []
        for job in self.store.pending_jobs():
            try:
                results.append(self.process_document(job.id))
            except Exception:
                failed = self.store.get_document(job.document_id)
                if failed is not None:
                    results.append(failed)
        return results

    def extract_content_blocks(
        self, document_id: str, page: int | None = None, kind: str | None = None
    ) -> list[ContentBlock]:
        document = self.store.get_document(document_id)
        if document is None:
            raise KeyError(document_id)
        return self.store.get_content_blocks(document_id, page=page, kind=kind)

    def extract_questions(
        self,
        document_id: str,
        taxonomy_node_id: str | None = None,
        page: int | None = None,
        classification_status: ClassificationStatus | None = None,
        include_descendants: bool = False,
    ) -> list[QuestionCandidate]:
        document = self.store.get_document(document_id)
        if document is None:
            raise KeyError(document_id)

        source_path = self.storage_dir / f"{document_id}.pdf"
        if not source_path.is_file():
            raise FileNotFoundError(document_id)

        actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual_hash != document.sha256:
            raise ValueError("Source PDF hash does not match recorded provenance")

        pages = extract_document(str(source_path))
        if len(pages) != document.page_count:
            raise ValueError("Source PDF page count does not match recorded metadata")

        taxonomy_node_ids: list[str] | None = None
        if taxonomy_node_id is not None:
            try:
                taxonomy_node_ids = self.taxonomy.descendant_ids(
                    taxonomy_node_id,
                    include_self=True,
                ) if include_descendants else [self.taxonomy.require(taxonomy_node_id).id]
            except KeyError as exc:
                raise ValueError(f"Unknown taxonomy node: {taxonomy_node_id}") from exc

        return self.store.get_questions(
            document_id,
            taxonomy_node_ids=taxonomy_node_ids,
            page=page,
            classification_status=classification_status,
        )


    def approve_taxonomy_proposal(
        self,
        proposal_id: str,
    ) -> TaxonomyProposalResolution:
        proposal = self.store.get_taxonomy_proposal(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)

        if proposal.status is not TaxonomyProposalStatus.PENDING:
            raise ValueError(
                f"Proposal {proposal.id} is already {proposal.status.value}"
            )

        effective = proposal
        if proposal.parent_id and proposal.parent_id.startswith("new:"):
            parent_proposal_id = f"{proposal.document_id}-{proposal.parent_id}"
            parent_proposal = self.store.get_taxonomy_proposal(parent_proposal_id)
            if parent_proposal is None:
                raise ValueError(
                    f"Parent proposal {proposal.parent_id!r} does not exist"
                )
            if parent_proposal.status is not TaxonomyProposalStatus.APPROVED:
                raise ValueError(
                    f"Parent proposal {parent_proposal.id!r} must be approved first"
                )
            if parent_proposal.resolved_node_id is None:
                raise ValueError(
                    f"Parent proposal {parent_proposal.id!r} has no resolved taxonomy node"
                )
            effective = proposal.model_copy(
                update={"parent_id": parent_proposal.resolved_node_id}
            )

        resolution = self.registry.approve(effective)
        self.store.resolve_taxonomy_proposal(
            proposal.id,
            TaxonomyProposalStatus.APPROVED,
            resolution.node_id,
            resolution.reason,
        )
        self.taxonomy = self.registry.refresh()
        self._reclassify_document_questions(proposal.document_id)
        return TaxonomyProposalResolution(
            proposal_id=proposal.id,
            status=TaxonomyProposalStatus.APPROVED,
            resolved_node_id=resolution.node_id,
            created=resolution.created,
            reason=resolution.reason,
        )

    def reject_taxonomy_proposal(
        self,
        proposal_id: str,
        reason: str = "Rejected during taxonomy review",
    ) -> TaxonomyProposalResolution:
        proposal = self.store.get_taxonomy_proposal(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        if proposal.status is not TaxonomyProposalStatus.PENDING:
            raise ValueError(
                f"Proposal {proposal.id} is already {proposal.status.value}"
            )
        clean_reason = reason.strip() or "Rejected during taxonomy review"
        self.store.resolve_taxonomy_proposal(
            proposal.id,
            TaxonomyProposalStatus.REJECTED,
            None,
            clean_reason,
        )
        return TaxonomyProposalResolution(
            proposal_id=proposal.id,
            status=TaxonomyProposalStatus.REJECTED,
            reason=clean_reason,
        )

    def _reclassify_document_questions(self, document_id: str) -> None:
        questions = self.store.get_questions(document_id)
        if not questions:
            return
        updated: list[QuestionCandidate] = []
        for question in questions:
            result = self.classifier.classify(question, self.taxonomy)
            updated.append(
                question.model_copy(
                    update={
                        "taxonomy_node_id": result.taxonomy_node_id,
                        "classification_status": (
                            ClassificationStatus.QUARANTINED
                            if result.quarantined
                            else ClassificationStatus.CLASSIFIED
                        ),
                        "classification_confidence": result.confidence,
                        "classification_reason": result.reason,
                    }
                )
            )
        self.store.replace_questions(document_id, updated)

    def propose_taxonomy(
        self,
        document_id: str,
    ) -> list:
        document = self.store.get_document(document_id)
        if document is None:
            raise KeyError(document_id)

        source_path = self.storage_dir / f"{document_id}.pdf"
        if not source_path.is_file():
            raise FileNotFoundError(document_id)

        actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual_hash != document.sha256:
            raise ValueError("Source PDF hash does not match recorded provenance")

        if self.taxonomy_proposal_provider is None:
            raise RuntimeError("No taxonomy AI provider is configured")

        pages = extract_document(str(source_path))
        if len(pages) != document.page_count:
            raise ValueError("Source PDF page count does not match recorded metadata")

        document_text = "\n\n".join(
            f"[Page {page.page_number}]\n{page.text}"
            for page in pages
            if page.text.strip()
        )
        proposals = TaxonomyProposalEngine(
            provider=self.taxonomy_proposal_provider,
            taxonomy=self.taxonomy,
        ).build_proposals(document.id, document_text)
        self.store.save_taxonomy_proposals(proposals)
        return proposals
