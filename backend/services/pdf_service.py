"""PDF processing service for extracting and chunking papers."""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.core.config import get_settings
from backend.services.vlm_service import get_vlm_service


@dataclass(frozen=True)
class ParsedPaperChunk:
    """One paragraph-aware chunk extracted from a paper."""

    content: str
    heading: str
    kind: str
    block_count: int
    block_counts: dict[str, int] = field(default_factory=dict)
    page_start: Optional[int] = None
    page_end: Optional[int] = None


@dataclass(frozen=True)
class ParsedPaper:
    """Docling parse output plus paragraph-aware chunks."""

    full_text: str
    chunks: list[ParsedPaperChunk]
    parser: str
    chunker: str
    table_blocks_removed: int
    table_chars_removed: int
    table_captions_added: int = 0
    figure_captions_added: int = 0
    caption_errors: int = 0


@dataclass(frozen=True)
class DoclingCaptionStats:
    """VLM caption replacement stats for Docling table/figure blocks."""

    table_captions_added: int = 0
    figure_captions_added: int = 0
    caption_errors: int = 0


@dataclass(frozen=True)
class _MarkdownBlock:
    """A logical Markdown block before final chunk merging."""

    kind: str
    heading: str
    text: str


class PDFService:
    """Service for processing PDF documents."""

    DOCLING_CHUNKER_NAME = "docling_markdown_paragraph_blocks"
    IMAGE_PLACEHOLDER = "<!-- image -->"
    _TABLE_BLOCK_PATTERN = re.compile(
        r"(?P<prefix>^|\n)(?P<table>[ \t]*\|[^\n]*\|[^\n]*(?:\n[ \t]*\|[^\n]*\|[^\n]*)+)",
        re.MULTILINE,
    )

    def __init__(self, vlm_service=None):
        self._docling_converter = None
        self._docling_converter_vlm_enabled: Optional[bool] = None
        self._vlm_service = vlm_service

    def parse_pdf(self, pdf_path) -> ParsedPaper:
        """Parse a PDF with Docling and create paragraph-aware chunks.

        Docling handles the PDF layout parsing. We export its document model to
        Markdown and apply the project chunk policy: paragraphs are the basic
        unit, adjacent short blocks under the same heading are merged, and
        Markdown tables are dropped unless they have been replaced by VLM
        captions during Docling document export.
        """
        pdf_path = Path(pdf_path)
        document = self._convert_with_docling(pdf_path)
        markdown, caption_stats = self.export_captioned_docling_markdown(document)
        parsed = self.chunk_docling_markdown(markdown, caption_stats=caption_stats)
        logger.info(
            f"Parsed {pdf_path.name} with Docling into {len(parsed.chunks)} chunks; "
            f"dropped {parsed.table_blocks_removed} table blocks; "
            f"captioned {parsed.table_captions_added} tables and "
            f"{parsed.figure_captions_added} figures"
        )
        return parsed

    def chunk_docling_markdown(
        self,
        markdown: str,
        target_chars: int = 2200,
        min_chars_before_split: int = 0,
        max_standalone_chars: int = 4200,
        caption_stats: Optional[DoclingCaptionStats] = None,
    ) -> ParsedPaper:
        """Chunk Docling Markdown by paragraph-like blocks and drop tables."""
        caption_stats = caption_stats or DoclingCaptionStats()
        if not markdown:
            return ParsedPaper(
                full_text="",
                chunks=[],
                parser="docling",
                chunker=self.DOCLING_CHUNKER_NAME,
                table_blocks_removed=0,
                table_chars_removed=0,
                table_captions_added=caption_stats.table_captions_added,
                figure_captions_added=caption_stats.figure_captions_added,
                caption_errors=caption_stats.caption_errors,
            )

        blocks, table_blocks_removed, table_chars_removed = self._markdown_blocks(markdown)
        normalized_blocks = self._normalize_blocks(blocks, target_chars, max_standalone_chars)
        chunks = self._merge_blocks_into_chunks(
            normalized_blocks,
            target_chars=target_chars,
            min_chars_before_split=min_chars_before_split,
        )
        full_text = "\n\n".join(chunk.content for chunk in chunks)
        return ParsedPaper(
            full_text=full_text,
            chunks=chunks,
            parser="docling",
            chunker=self.DOCLING_CHUNKER_NAME,
            table_blocks_removed=table_blocks_removed,
            table_chars_removed=table_chars_removed,
            table_captions_added=caption_stats.table_captions_added,
            figure_captions_added=caption_stats.figure_captions_added,
            caption_errors=caption_stats.caption_errors,
        )

    def _convert_with_docling(self, pdf_path: Path):
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            raise RuntimeError(
                "Docling is required for PDF parsing. Install project dependencies first."
            ) from e

        vlm_enabled = self._vlm_enabled()
        if (
            self._docling_converter is None
            or self._docling_converter_vlm_enabled != vlm_enabled
        ):
            if vlm_enabled:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import PdfFormatOption

                settings = get_settings()
                pipeline_options = PdfPipelineOptions()
                pipeline_options.generate_page_images = True
                pipeline_options.images_scale = settings.vlm_image_scale
                self._docling_converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_options=pipeline_options,
                        )
                    }
                )
            else:
                self._docling_converter = DocumentConverter()
            self._docling_converter_vlm_enabled = vlm_enabled
        result = self._docling_converter.convert(pdf_path)
        return result.document

    def export_captioned_docling_markdown(self, document: Any) -> tuple[str, DoclingCaptionStats]:
        """Export Docling Markdown, replacing tables/figures with VLM captions when enabled."""
        markdown = document.export_to_markdown(image_placeholder=self.IMAGE_PLACEHOLDER)
        vlm = self._get_vlm_service()
        if not getattr(vlm, "is_configured", False):
            return markdown, DoclingCaptionStats()

        table_captions_added = 0
        figure_captions_added = 0
        caption_errors = 0
        table_cursor = 0
        image_cursor = 0

        for item, _level in document.iterate_items(traverse_pictures=False):
            kind = self._caption_item_kind(item)
            if not kind:
                continue

            image = self._item_image(item, document)
            if image is None:
                caption_errors += 1
                if kind == "table":
                    table_cursor = self._advance_next_table(markdown, item, document, table_cursor)
                else:
                    image_cursor = self._advance_next_image(markdown, image_cursor)
                logger.warning(f"Skipping {kind} caption because Docling did not provide an image")
                continue

            prompt = self._vlm_caption_prompt(kind, item, document)
            caption = vlm.caption_image(image, prompt)
            if not caption:
                caption_errors += 1
                if kind == "table":
                    table_cursor = self._advance_next_table(markdown, item, document, table_cursor)
                else:
                    image_cursor = self._advance_next_image(markdown, image_cursor)
                continue

            caption_block = self._caption_markdown_block(kind, caption)
            if kind == "table":
                markdown, table_cursor, replaced = self._replace_next_table(
                    markdown,
                    item,
                    document,
                    caption_block,
                    table_cursor,
                )
                if replaced:
                    table_captions_added += 1
                else:
                    caption_errors += 1
                    logger.warning("Generated VLM table caption but could not replace table Markdown")
            else:
                markdown, image_cursor, replaced = self._replace_next_image(
                    markdown,
                    caption_block,
                    image_cursor,
                )
                if replaced:
                    figure_captions_added += 1
                else:
                    caption_errors += 1
                    logger.warning("Generated VLM figure caption but could not replace image placeholder")

        return markdown, DoclingCaptionStats(
            table_captions_added=table_captions_added,
            figure_captions_added=figure_captions_added,
            caption_errors=caption_errors,
        )

    def _get_vlm_service(self):
        if self._vlm_service is None:
            self._vlm_service = get_vlm_service()
        return self._vlm_service

    def _vlm_enabled(self) -> bool:
        return bool(getattr(self._get_vlm_service(), "is_configured", False))

    def _caption_item_kind(self, item: Any) -> Optional[str]:
        label = getattr(item, "label", "")
        label_value = getattr(label, "value", label)
        if label_value == "table":
            return "table"
        if label_value in {"picture", "chart"}:
            return "figure"
        return None

    def _item_image(self, item: Any, document: Any) -> Any:
        try:
            return item.get_image(document)
        except Exception as e:
            logger.warning(f"Failed to extract Docling item image: {e}")
            return None

    def _vlm_caption_prompt(self, kind: str, item: Any, document: Any) -> str:
        native_caption = self._native_caption(item, document)
        if kind == "table":
            table_markdown = self._item_markdown(item, document)
            context = self._truncate_context(table_markdown)
            return (
                "Caption this scientific paper table for retrieval and Q&A. "
                "Mention the main variables, methods, metrics, important numeric "
                "comparisons, and the overall takeaway. Be faithful to the image; "
                "do not invent values. Return 3-6 concise sentences.\n\n"
                f"Existing caption: {native_caption or 'N/A'}\n"
                f"Docling table text:\n{context or 'N/A'}"
            )

        return (
            "Caption this scientific paper figure for retrieval and Q&A. "
            "Describe what the figure shows, its axes or components when visible, "
            "the main trend or result, and any labels that matter. Be faithful to "
            "the image and return 3-6 concise sentences.\n\n"
            f"Existing caption: {native_caption or 'N/A'}"
        )

    def _native_caption(self, item: Any, document: Any) -> str:
        try:
            return (item.caption_text(document) or "").strip()
        except Exception:
            return ""

    def _item_markdown(self, item: Any, document: Any) -> str:
        try:
            return (item.export_to_markdown(document) or "").strip()
        except Exception:
            return ""

    def _truncate_context(self, text: str, max_chars: int = 4000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit("\n", 1)[0] + "\n..."

    def _caption_markdown_block(self, kind: str, caption: str) -> str:
        normalized = " ".join(caption.split())
        prefix = "Table caption" if kind == "table" else "Figure caption"
        return f"{prefix}: {normalized}"

    def _replace_next_table(
        self,
        markdown: str,
        item: Any,
        document: Any,
        replacement: str,
        start_index: int,
    ) -> tuple[str, int, bool]:
        item_markdown = self._item_markdown(item, document)
        found = self._find_next_table(markdown, item_markdown, start_index)
        if found is None:
            return markdown, start_index, False
        start, end = found
        updated = f"{markdown[:start]}{replacement}{markdown[end:]}"
        return updated, start + len(replacement), True

    def _advance_next_table(
        self,
        markdown: str,
        item: Any,
        document: Any,
        start_index: int,
    ) -> int:
        item_markdown = self._item_markdown(item, document)
        found = self._find_next_table(markdown, item_markdown, start_index)
        if found is None:
            return start_index
        return found[1]

    def _find_next_table(
        self,
        markdown: str,
        item_markdown: str,
        start_index: int,
    ) -> Optional[tuple[int, int]]:
        if item_markdown:
            exact_start = markdown.find(item_markdown, start_index)
            if exact_start >= 0:
                return exact_start, exact_start + len(item_markdown)

        match = self._TABLE_BLOCK_PATTERN.search(markdown, start_index)
        if not match:
            return None
        return match.start("table"), match.end("table")

    def _replace_next_image(
        self,
        markdown: str,
        replacement: str,
        start_index: int,
    ) -> tuple[str, int, bool]:
        image_start = markdown.find(self.IMAGE_PLACEHOLDER, start_index)
        if image_start < 0:
            return markdown, start_index, False
        image_end = image_start + len(self.IMAGE_PLACEHOLDER)
        updated = f"{markdown[:image_start]}{replacement}{markdown[image_end:]}"
        return updated, image_start + len(replacement), True

    def _advance_next_image(self, markdown: str, start_index: int) -> int:
        image_start = markdown.find(self.IMAGE_PLACEHOLDER, start_index)
        if image_start < 0:
            return start_index
        return image_start + len(self.IMAGE_PLACEHOLDER)

    def _markdown_blocks(self, markdown: str) -> tuple[list[_MarkdownBlock], int, int]:
        blocks: list[_MarkdownBlock] = []
        table_blocks_removed = 0
        table_chars_removed = 0
        current_heading = "Document"
        active_kind: Optional[str] = None
        active_lines: list[str] = []

        def flush_active() -> None:
            nonlocal active_kind, active_lines, table_blocks_removed, table_chars_removed
            if not active_kind or not active_lines:
                active_kind = None
                active_lines = []
                return

            text = "\n".join(active_lines).strip()
            if text:
                if active_kind == "table":
                    table_blocks_removed += 1
                    table_chars_removed += len(text)
                else:
                    blocks.append(_MarkdownBlock(active_kind, current_heading, text))
            active_kind = None
            active_lines = []

        for raw_line in markdown.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
            if heading_match:
                flush_active()
                current_heading = heading_match.group(2).strip()
                continue

            if not stripped:
                flush_active()
                continue

            kind = self._markdown_line_kind(stripped, active_kind)
            if active_kind and kind != active_kind:
                flush_active()

            active_kind = kind
            active_lines.append(line)

        flush_active()
        return blocks, table_blocks_removed, table_chars_removed

    def _markdown_line_kind(self, stripped_line: str, active_kind: Optional[str]) -> str:
        if self._is_table_line(stripped_line):
            return "table"
        if self._is_list_start(stripped_line):
            return "list"
        if active_kind == "list" and not self._looks_like_paragraph_start(stripped_line):
            return "list"
        return "paragraph"

    def _is_table_line(self, stripped_line: str) -> bool:
        return stripped_line.startswith("|") and stripped_line.count("|") >= 2

    def _is_list_start(self, stripped_line: str) -> bool:
        return bool(re.match(r"^([-*+]|\d+[.)])\s+", stripped_line))

    def _looks_like_paragraph_start(self, stripped_line: str) -> bool:
        return bool(re.match(r"^[A-Z][A-Za-z0-9 ,;:'\"()\[\]-]{12,}", stripped_line))

    def _normalize_blocks(
        self,
        blocks: list[_MarkdownBlock],
        target_chars: int,
        max_standalone_chars: int,
    ) -> list[_MarkdownBlock]:
        normalized: list[_MarkdownBlock] = []
        for block in blocks:
            if block.kind == "list" and len(block.text) > target_chars:
                normalized.extend(self._split_list_block(block, target_chars))
            elif len(block.text) <= max_standalone_chars:
                normalized.append(block)
            else:
                normalized.extend(self._split_long_text_block(block, target_chars))
        return normalized

    def _split_list_block(
        self,
        block: _MarkdownBlock,
        target_chars: int,
    ) -> list[_MarkdownBlock]:
        items = self._list_items(block.text)
        if not items:
            return self._split_long_text_block(block, target_chars)

        split_blocks: list[_MarkdownBlock] = []
        current: list[str] = []
        current_len = 0
        for item in items:
            item_len = len(item)
            if current and current_len + item_len + 2 > target_chars:
                split_blocks.append(_MarkdownBlock(block.kind, block.heading, "\n".join(current)))
                current = []
                current_len = 0
            current.append(item)
            current_len += item_len + 1

        if current:
            split_blocks.append(_MarkdownBlock(block.kind, block.heading, "\n".join(current)))
        return split_blocks

    def _list_items(self, text: str) -> list[str]:
        text = re.sub(r"\s+-\s+(\[\s*\d+\s*\])", r"\n- \1", text)
        items: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if self._is_list_start(line.strip()):
                if current:
                    items.append("\n".join(current).strip())
                current = [line]
            elif current:
                current.append(line)

        if current:
            items.append("\n".join(current).strip())
        return [item for item in items if item]

    def _split_long_text_block(
        self,
        block: _MarkdownBlock,
        target_chars: int,
    ) -> list[_MarkdownBlock]:
        pieces = re.split(r"(?<=[.!?])\s+", block.text)
        split_blocks: list[_MarkdownBlock] = []
        current: list[str] = []
        current_len = 0

        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if current and current_len + len(piece) + 1 > target_chars:
                split_blocks.append(_MarkdownBlock(block.kind, block.heading, " ".join(current)))
                current = []
                current_len = 0
            current.append(piece)
            current_len += len(piece) + 1

        if current:
            split_blocks.append(_MarkdownBlock(block.kind, block.heading, " ".join(current)))
        return split_blocks or [block]

    def _merge_blocks_into_chunks(
        self,
        blocks: list[_MarkdownBlock],
        target_chars: int,
        min_chars_before_split: int,
    ) -> list[ParsedPaperChunk]:
        chunks: list[ParsedPaperChunk] = []
        current: list[_MarkdownBlock] = []

        def current_len() -> int:
            return sum(len(block.text) for block in current) + max(0, len(current) - 1) * 2

        def flush_current() -> None:
            nonlocal current
            if not current:
                return
            text = "\n\n".join(block.text for block in current).strip()
            block_counts = Counter(block.kind for block in current)
            kind = current[0].kind if len(block_counts) == 1 else "mixed"
            chunks.append(
                ParsedPaperChunk(
                    content=text,
                    heading=current[0].heading,
                    kind=kind,
                    block_count=len(current),
                    block_counts=dict(block_counts),
                )
            )
            current = []

        for block in blocks:
            if not current:
                current = [block]
                continue

            same_heading = block.heading == current[0].heading
            merged_len = current_len() + len(block.text) + 2
            should_merge = same_heading and (
                merged_len <= target_chars
                or (
                    min_chars_before_split > 0
                    and current_len() < min_chars_before_split
                    and len(block.text) < min_chars_before_split
                )
            )

            if should_merge:
                current.append(block)
            else:
                flush_current()
                current = [block]

        flush_current()
        return chunks

    def extract_sections(self, text: str) -> dict[str, str]:
        """Extract common paper sections from text.

        Args:
            text: Full paper text

        Returns:
            Dictionary mapping section names to content
        """
        sections = {}
        section_markers = [
            "abstract",
            "introduction",
            "related work",
            "background",
            "methodology",
            "method",
            "approach",
            "experiments",
            "results",
            "discussion",
            "conclusion",
            "references",
        ]

        lines = text.split("\n")
        current_section = "preamble"
        current_content = []

        for line in lines:
            line_lower = line.lower().strip()

            found_section = None
            for marker in section_markers:
                if marker in line_lower and (
                    line_lower.startswith(marker)
                    or line_lower.startswith("1.")
                    or line_lower.startswith("i.")
                    or line_lower.startswith("#")
                ):
                    found_section = marker
                    break

            if found_section:
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = found_section
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections


_pdf_service: Optional[PDFService] = None


def get_pdf_service() -> PDFService:
    """Get or create PDF service singleton."""
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PDFService()
    return _pdf_service
