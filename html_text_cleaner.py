"""
HTML Text Cleaner for RAG System

This module provides robust HTML text extraction and cleaning utilities
for the LinkedIn Article Generator RAG system. It handles HTML parsing,
removes scaffolding content, and applies intelligent size limiting.
"""

from bs4 import BeautifulSoup, Comment, Tag
import re
import logging
from typing import List, Tuple, Optional, Union
from html import unescape
import dspy
from dspy_factory import get_current_lm, get_context_window, check_context_usage


class CitationFilter(dspy.Signature):
    """Extract only the most citation-worthy sentences from a passage."""

    passage: str = dspy.InputField(desc="HTML cleaned text passage")
    quality_sentences: str = dspy.OutputField(
        desc="Filtered passage keeping sentences with quantifiable data, statistics, or references"
    )


class CitationWorthyFilter(dspy.Module):
    """DSPy module that filters passages to extract only citation-worthy content."""

    def __init__(self):
        super().__init__()
        self.filter = dspy.Predict(CitationFilter)

    def forward(self, passages: List[str]) -> List[str]:
        """
        Filter passages individually to extract only citation-worthy sentences.
        Processes each passage separately to avoid context window overflow.

        Args:
            passages: List of cleaned text passages

        Returns:
            List of passages containing only citation-worthy sentences
        """
        if not passages:
            return []

        filtered_passages = []
        logger = logging.getLogger(__name__)

        print(
            f"🔍 Processing {len(passages)} passages individually for citation filtering..."
        )

        for i, passage in enumerate(passages):
            try:
                # Process single passage to avoid context overflow
                result = self.filter(passage=passage)
                if result.quality_sentences and result.quality_sentences.strip():
                    filtered_passages.append(result.quality_sentences)
                    print(f"  ✅ Passage {i+1}: Passage filtered successfully")
                    print(
                        f"    📄 Filtered content(len:{len(result.quality_sentences)}): {result.quality_sentences[:400]}..."
                    )
                else:
                    # If no citation-worthy content found, keep original
                    filtered_passages.append(passage)
                    print(
                        f"  📄 Passage {i+1}: No citation filtering applied, kept original"
                    )

            except Exception as e:
                logger.warning(f"Citation filtering failed for passage {i+1}: {e}")
                # If filtering fails, keep original passage
                filtered_passages.append(passage)
                print(f"  ⚠️  Passage {i+1}: Filtering failed, kept original")

        print(
            f"🎯 Citation filtering completed: {len(filtered_passages)} passages processed"
        )
        return filtered_passages


class HTMLTextCleaner:
    """
    Robust HTML text extraction and cleaning utility.
    Handles all exceptions gracefully and returns empty string on unrecoverable errors.
    """

    def __init__(
        self, min_content_length: int = 200, max_total_chars: Optional[int] = None
    ):
        """
        Initialize the HTML text cleaner.

        Args:
            min_content_length: Minimum length for content to be considered meaningful
            max_total_chars: Maximum total characters across all passages.
                           If None, auto-calculated based on context window.
        """
        self.min_content_length = min_content_length

        # Use context window management for intelligent sizing
        if max_total_chars is None:
            try:
                # Reserve space for prompts and output, use 50% of context for cleaned content
                context_window = get_context_window()
                lm = get_current_lm()
                available_for_content = int(
                    (context_window - lm.get_max_output_tokens()) * 0.5
                )
                max_total_chars = max(50000, available_for_content)  # Minimum 50K chars
                self.logger.info(
                    f"🧠 Auto-sizing HTML cleaner to {max_total_chars:,} chars based on {context_window:,} token context window"
                )
            except Exception as e:
                self.logger.warning(
                    f"Could not determine context window, using default: {e}"
                )
                max_total_chars = 50000

        self.max_total_chars = max_total_chars
        self.logger = logging.getLogger(__name__)
        self.citation_filter = CitationWorthyFilter()

        # Calculate safe passage size for DSPy processing
        self.max_passage_size = self._calculate_max_passage_size()

        # Unwanted HTML tags to remove entirely
        self.unwanted_tags = [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "advertisement",
            "ads",
            "sidebar",
            "menu",
            "breadcrumb",
            "social-share",
            "comments",
            "related-posts",
            "newsletter",
            "popup",
            "modal",
            "cookie-banner",
            "privacy-notice",
            "iframe",
            "embed",
            "object",
            "form",
            "input",
            "button",
        ]

        # Class/ID patterns that indicate scaffolding content
        self.unwanted_patterns = [
            "nav",
            "menu",
            "header",
            "footer",
            "sidebar",
            "ad",
            "advertisement",
            "social",
            "share",
            "comment",
            "related",
            "newsletter",
            "subscribe",
            "popup",
            "modal",
            "cookie",
            "privacy",
            "breadcrumb",
            "pagination",
            "meta",
            "tag",
            "category",
            "author-bio",
            "byline",
            "widget",
        ]

        # Selectors for main content areas (in order of preference)
        self.main_content_selectors = [
            "main",
            "article",
            '[role="main"]',
            ".content",
            ".post-content",
            ".article-content",
            ".entry-content",
            ".post-body",
            ".story-body",
            ".main-content",
            ".primary-content",
            ".article-body",
        ]

        # Common web artifacts to remove
        self.web_artifacts = [
            r"Skip to main content",
            r"Skip to navigation",
            r"Cookie policy",
            r"Privacy policy",
            r"Terms of service",
            r"Subscribe to newsletter",
            r"Follow us on \w+",
            r"Share this article",
            r"Related articles?",
            r"Advertisement",
            r"Sponsored content",
            r"Loading\.{3}",
            r"Click here to \w+",
            r"Read more",
            r"Show more",
            r"View all",
            r"Sign up",
            r"Log in",
            r"\d+\s*comments?",
            r"\d+\s*shares?",
            r"\d+\s*likes?",
            r"Published on \w+",
            r"Updated on \w+",
            r"By \w+ \w+",
            r"Tags?:.*",
            r"Categories?:.*",
            r"Copyright.*",
            r"All rights reserved",
        ]

    def clean_passage(self, html_content: str) -> str:
        """
        Clean a single HTML passage and extract meaningful text.

        Args:
            html_content: Raw HTML content to clean

        Returns:
            Cleaned text content or empty string if cleaning fails
        """
        try:
            if not html_content or not isinstance(html_content, str):
                return ""

            # Handle HTML entities first
            try:
                html_content = unescape(html_content)
            except Exception as e:
                self.logger.warning(f"Failed to unescape HTML entities: {e}")
                # Continue with original content

            # Parse with Beautiful Soup
            soup = self._parse_html(html_content)
            if not soup:
                return ""

            # Remove unwanted elements
            self._remove_unwanted_elements(soup)

            # Extract main content
            main_content = self._extract_main_content(soup)

            # Convert to structured text
            text = self._extract_structured_text(main_content)

            # Final text cleanup
            cleaned_text = self._clean_extracted_text(text)

            return cleaned_text if len(cleaned_text) >= self.min_content_length else ""

        except Exception as e:
            self.logger.error(f"Unrecoverable error in clean_passage: {e}")
            return ""

    def _calculate_max_passage_size(self) -> int:
        """Calculate maximum size for individual passages to fit in DSPy context window."""
        try:
            lm = get_current_lm()
            context_window = lm.get_context_window()

            # Reserve space for:
            # - DSPy prompt instructions (~500 tokens)
            # - Input/output formatting (~200 tokens)
            # - Safety margin (~300 tokens)
            overhead_tokens = 1000

            # Convert to characters (rough: 1 token ≈ 4 chars)
            overhead_chars = overhead_tokens * 4

            # Use remaining space for passage content
            max_passage_chars = (
                context_window * 4 - overhead_chars - lm.get_max_output_tokens() * 4
            )

            # Ensure reasonable minimum and maximum
            max_passage_chars = max(5000, min(max_passage_chars, 50000))

            self.logger.info(
                f"🧠 Max passage size for DSPy: {max_passage_chars:,} chars "
                f"(context: {context_window:,} tokens)"
            )

            return max_passage_chars

        except Exception as e:
            self.logger.warning(f"Could not calculate max passage size: {e}")
            return 20000  # Conservative fallback

    def _preprocess_passages_for_dspy(self, passages: List[str]) -> List[str]:
        """Ensure each passage fits in DSPy context window before citation filtering."""
        processed_passages = []

        print(
            f"🔍 Pre-processing {len(passages)} passages for DSPy (max size: {self.max_passage_size:,} chars)..."
        )

        for i, passage in enumerate(passages):
            if len(passage) <= self.max_passage_size:
                processed_passages.append(passage)
            else:
                # Truncate intelligently while preserving meaning
                truncated = self._truncate_intelligently(passage, self.max_passage_size)
                processed_passages.append(truncated)
                print(
                    f"  ✂️  Passage {i+1}: Truncated from {len(passage):,} to {len(truncated):,} chars for DSPy processing"
                )

        return processed_passages

    def clean_and_limit_passages(
        self, passages: List[str], urls: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Clean multiple passages and apply size limiting.

        Args:
            passages: List of raw HTML passages
            urls: Corresponding URLs for the passages

        Returns:
            Tuple of (cleaned_passages, corresponding_urls)
        """
        try:
            if not passages or not urls or len(passages) != len(urls):
                self.logger.warning(
                    "Invalid input: passages and urls must be non-empty lists of equal length"
                )
                return [], []

            cleaned_passages = []
            cleaned_urls = []

            print(f"🧹 Cleaning {len(passages)} passages...")

            for i, (passage, url) in enumerate(zip(passages, urls)):
                try:
                    original_length = len(passage) if passage else 0
                    cleaned = self.clean_passage(passage)

                    if cleaned:  # Only keep non-empty cleaned passages
                        cleaned_passages.append(cleaned)
                        cleaned_urls.append(url)

                        reduction = (
                            ((original_length - len(cleaned)) / original_length) * 100
                            if original_length > 0
                            else 0
                        )
                        print(
                            f"  📄 Passage {i+1}: {original_length:,} → {len(cleaned):,} chars ({reduction:.1f}% reduction)"
                        )
                    else:
                        print(
                            f"  🗑️ Passage {i+1}: Removed (insufficient content after cleaning)"
                        )

                except Exception as e:
                    self.logger.error(f"Error cleaning passage {i+1}: {e}")
                    continue

            # Apply size limiting if needed
            return self._apply_size_limiting(cleaned_passages, cleaned_urls)

        except Exception as e:
            self.logger.error(f"Unrecoverable error in clean_and_limit_passages: {e}")
            return [], []

    def _parse_html(self, html_content: str) -> Optional[BeautifulSoup]:
        """Parse HTML content with fallback parsers."""
        parsers = ["lxml", "html.parser", "html5lib"]

        for parser in parsers:
            try:
                soup = BeautifulSoup(html_content, parser)
                return soup
            except Exception as e:
                self.logger.warning(f"Failed to parse with {parser}: {e}")
                continue

        self.logger.error("All HTML parsers failed")
        return None

    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove unwanted HTML elements from the soup."""
        try:
            # Remove unwanted tags entirely
            for tag in self.unwanted_tags:
                try:
                    for element in soup.find_all(tag):
                        element.decompose()
                except Exception as e:
                    self.logger.warning(f"Error removing tag {tag}: {e}")

            # Remove elements by class/id patterns
            for pattern in self.unwanted_patterns:
                try:
                    # Remove by class
                    for element in soup.find_all(class_=re.compile(pattern, re.I)):
                        element.decompose()
                    # Remove by id
                    for element in soup.find_all(id=re.compile(pattern, re.I)):
                        element.decompose()
                except Exception as e:
                    self.logger.warning(f"Error removing pattern {pattern}: {e}")

            # Remove HTML comments
            try:
                for comment in soup.find_all(
                    string=lambda text: isinstance(text, Comment)
                ):
                    comment.extract()
            except Exception as e:
                self.logger.warning(f"Error removing comments: {e}")

        except Exception as e:
            self.logger.error(f"Error in _remove_unwanted_elements: {e}")

    def _extract_main_content(self, soup: BeautifulSoup) -> Union[BeautifulSoup, Tag]:
        """Extract main content area or return full soup if not found."""
        try:
            for selector in self.main_content_selectors:
                try:
                    main_content = soup.select_one(selector)
                    if main_content:
                        self.logger.debug(
                            f"Found main content with selector: {selector}"
                        )
                        return main_content
                except Exception as e:
                    self.logger.warning(f"Error with selector {selector}: {e}")

            # If no main content found, return the whole soup
            return soup

        except Exception as e:
            self.logger.error(f"Error in _extract_main_content: {e}")
            return soup

    def _extract_structured_text(self, soup: Union[BeautifulSoup, Tag]) -> str:
        """Extract text while preserving some structure."""
        try:
            text_parts = []

            # Process different elements to maintain structure
            for element in soup.find_all(
                ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "div"]
            ):
                try:
                    text = element.get_text(strip=True)
                    if text and len(text) > 10:  # Only meaningful text
                        # Check if element has name attribute (it should for Tag objects)
                        element_name = getattr(element, "name", None)
                        if element_name:
                            # Add extra spacing for headers
                            if element_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                                text_parts.append(f"\n{text}\n")
                            # Add spacing for paragraphs and quotes
                            elif element_name in ["p", "blockquote", "div"]:
                                text_parts.append(f"{text}\n")
                            # List items
                            elif element_name == "li":
                                text_parts.append(f"• {text}\n")
                        else:
                            # Fallback for elements without name
                            text_parts.append(f"{text}\n")
                except Exception as e:
                    self.logger.warning(f"Error extracting text from element: {e}")
                    continue

            # If no structured content found, fall back to all text
            if not text_parts:
                try:
                    return soup.get_text(separator=" ", strip=True)
                except Exception as e:
                    self.logger.error(f"Error in fallback text extraction: {e}")
                    return ""

            return "\n".join(text_parts)

        except Exception as e:
            self.logger.error(f"Error in _extract_structured_text: {e}")
            return ""

    def _clean_extracted_text(self, text: str) -> str:
        """Final cleanup of extracted text."""
        try:
            if not text:
                return ""

            # Remove web artifacts
            for pattern in self.web_artifacts:
                try:
                    text = re.sub(pattern, "", text, flags=re.IGNORECASE)
                except Exception as e:
                    self.logger.warning(f"Error removing pattern {pattern}: {e}")

            # Clean up whitespace
            try:
                text = re.sub(
                    r"\n\s*\n\s*\n+", "\n\n", text
                )  # Multiple newlines to double
                text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single
                text = re.sub(r"^\s+|\s+$", "", text, flags=re.MULTILINE)  # Trim lines
            except Exception as e:
                self.logger.warning(f"Error cleaning whitespace: {e}")

            # Filter meaningful lines
            try:
                lines = text.split("\n")
                meaningful_lines = []

                for line in lines:
                    line = line.strip()

                    # Keep lines with substantial content
                    if len(line) > 15 and not line.isupper():
                        # Skip lines that are mostly punctuation
                        if len(re.sub(r"[^\w\s]", "", line)) > len(line) * 0.5:
                            meaningful_lines.append(line)

                return "\n".join(meaningful_lines).strip()

            except Exception as e:
                self.logger.error(f"Error filtering lines: {e}")
                return text.strip()

        except Exception as e:
            self.logger.error(f"Error in _clean_extracted_text: {e}")
            return ""

    def _apply_size_limiting(
        self, passages: List[str], urls: List[str]
    ) -> Tuple[List[str], List[str]]:
        """Apply smart size limiting to stay under character limit."""
        try:
            total_chars = sum(len(p) for p in passages)
            print(f"📊 Total after cleaning: {total_chars:,} characters")

            if total_chars <= self.max_total_chars:
                print(f"✅ Within limit after cleaning!")
                return passages, urls

            print(f"⚠️ Over limit, applying smart truncation...")

            # Pre-process passages to ensure they fit in DSPy context window
            preprocessed_passages = self._preprocess_passages_for_dspy(passages)

            # Apply citation filtering to extract only citation-worthy content
            print(
                f"🎯 Applying citation filtering to {len(preprocessed_passages)} passages..."
            )
            citation_passages = self.citation_filter(preprocessed_passages)

            # Check if citation filtering helped reduce size
            citation_total = sum(len(p) for p in citation_passages)
            print(
                f"📊 After citation filtering: {citation_total:,} characters ({len(citation_passages)} passages)"
            )

            # If citation filtering brought us under the limit, we're done
            if citation_total <= self.max_total_chars:
                print(f"✅ Citation filtering brought us within limit!")
                return citation_passages, urls[: len(citation_passages)]

            # Otherwise, continue with smart truncation on citation-filtered passages
            print(
                f"⚠️ Still over limit, applying smart truncation to citation-filtered content..."
            )

            # Smart truncation: prioritize by length and position
            passage_data = []
            for i, (passage, url) in enumerate(
                zip(citation_passages, urls[: len(citation_passages)])
            ):
                relevance_score = len(passage) * (
                    1 - i * 0.1
                )  # Slight penalty for later results
                passage_data.append(
                    {
                        "passage": passage,
                        "url": url,
                        "length": len(passage),
                        "score": relevance_score,
                        "index": i,
                    }
                )

            # Sort by relevance score
            passage_data.sort(key=lambda x: x["score"], reverse=True)

            # Select passages up to the limit
            selected_passages = []
            selected_urls = []
            running_total = 0

            for data in passage_data:
                passage = data["passage"]
                url = data["url"]

                if running_total + len(passage) <= self.max_total_chars:
                    selected_passages.append(passage)
                    selected_urls.append(url)
                    running_total += len(passage)
                else:
                    # Try to fit a truncated version
                    remaining_chars = self.max_total_chars - running_total
                    if remaining_chars > 500:  # Only if meaningful amount remains
                        truncated = self._truncate_intelligently(
                            passage, remaining_chars
                        )
                        if truncated:
                            selected_passages.append(truncated)
                            selected_urls.append(url)
                    break

            final_total = sum(len(p) for p in selected_passages)
            print(
                f"📊 Final total: {final_total:,} characters ({len(selected_passages)} passages)"
            )

            return selected_passages, selected_urls

        except Exception as e:
            self.logger.error(f"Error in _apply_size_limiting: {e}")
            return passages[:1] if passages else [], (
                urls[:1] if urls else []
            )  # Fallback to first passage

    def _truncate_intelligently(self, text: str, max_chars: int) -> str:
        """Truncate text at sentence boundaries when possible."""
        try:
            if len(text) <= max_chars:
                return text

            # Try to cut at sentence boundaries
            sentences = text.split(". ")
            truncated = ""

            for sentence in sentences:
                if len(truncated) + len(sentence) + 2 <= max_chars:
                    truncated += sentence + ". "
                else:
                    break

            # If no complete sentences fit, do word-level truncation
            if not truncated.strip():
                words = text.split()
                truncated = ""
                for word in words:
                    if len(truncated) + len(word) + 1 <= max_chars - 3:  # -3 for "..."
                        truncated += word + " "
                    else:
                        break

            result = truncated.strip()
            return result + "..." if result and result != text else result

        except Exception as e:
            self.logger.error(f"Error in _truncate_intelligently: {e}")
            return text[: max_chars - 3] + "..." if len(text) > max_chars else text
