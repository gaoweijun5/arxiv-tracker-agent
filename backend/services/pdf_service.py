"""PDF processing service for extracting and chunking papers."""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


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


@dataclass(frozen=True)
class _MarkdownBlock:
    """A logical Markdown block before final chunk merging."""

    kind: str
    heading: str
    text: str


class PDFService:
    """Service for processing PDF documents."""

    DOCLING_CHUNKER_NAME = "docling_markdown_paragraph_blocks"

    def __init__(self):
        self._docling_converter = None

    def parse_pdf(self, pdf_path) -> ParsedPaper:
        """Parse a PDF with Docling and create paragraph-aware chunks.

        Docling handles the PDF layout parsing. We export its document model to
        Markdown and apply the project chunk policy: paragraphs are the basic
        unit, adjacent short blocks under the same heading are merged, and
        Markdown tables are dropped instead of indexed as chunks.
        """
        pdf_path = Path(pdf_path)
        document = self._convert_with_docling(pdf_path)
        markdown = document.export_to_markdown()
        parsed = self.chunk_docling_markdown(markdown)
        logger.info(
            f"Parsed {pdf_path.name} with Docling into {len(parsed.chunks)} chunks; "
            f"dropped {parsed.table_blocks_removed} table blocks"
        )
        return parsed

    def chunk_docling_markdown(
        self,
        markdown: str,
        target_chars: int = 2200,
        min_chars_before_split: int = 0,
        max_standalone_chars: int = 4200,
    ) -> ParsedPaper:
        """Chunk Docling Markdown by paragraph-like blocks and drop tables."""
        if not markdown:
            return ParsedPaper(
                full_text="",
                chunks=[],
                parser="docling",
                chunker=self.DOCLING_CHUNKER_NAME,
                table_blocks_removed=0,
                table_chars_removed=0,
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
        )

    def _convert_with_docling(self, pdf_path: Path):
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            raise RuntimeError(
                "Docling is required for PDF parsing. Install project dependencies first."
            ) from e

        if self._docling_converter is None:
            self._docling_converter = DocumentConverter()
        result = self._docling_converter.convert(pdf_path)
        return result.document

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
