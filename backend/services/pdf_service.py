"""PDF processing service for extracting text from papers."""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from loguru import logger


class PDFService:
    """Service for processing PDF documents."""

    def extract_text(self, pdf_path) -> Optional[str]:
        """Extract text content from a PDF file.

        Args:
            pdf_path: Path to PDF file (str or Path)

        Returns:
            Extracted text or None if failed
        """
        pdf_path = Path(pdf_path)
        try:
            doc = fitz.open(str(pdf_path))
            text_parts = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"[Page {page_num + 1}]\n{text}")

            doc.close()
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} chars from {pdf_path.name}")
            return full_text

        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return None

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[str]:
        """Split text into overlapping chunks.

        Args:
            text: Text to chunk
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size

            # Try to find a good break point
            if end < text_len:
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    sent_break = max(
                        text.rfind(". ", start, end),
                        text.rfind("? ", start, end),
                        text.rfind("! ", start, end),
                    )
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - chunk_overlap

        logger.info(f"Split text into {len(chunks)} chunks")
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

            # Check if this line is a section header
            found_section = None
            for marker in section_markers:
                if marker in line_lower and (
                    line_lower.startswith(marker)
                    or line_lower.startswith(f"1.")
                    or line_lower.startswith(f"i.")
                    or line_lower.startswith("#")
                ):
                    found_section = marker
                    break

            if found_section:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = found_section
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections


# Singleton instance
_pdf_service: Optional[PDFService] = None


def get_pdf_service() -> PDFService:
    """Get or create PDF service singleton."""
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PDFService()
    return _pdf_service
