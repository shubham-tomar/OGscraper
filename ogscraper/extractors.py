"""
Multiple content extraction strategies with fallbacks
"""

import logging
from typing import Optional, Dict, Any, Union

import requests
import trafilatura
from bs4 import BeautifulSoup
from readability.readability import Document

from .models import ScrapedItem
from .renderer import sync_render_page


logger = logging.getLogger(__name__)


class MultiExtractor:
    """Multi-strategy content extractor with fallbacks"""

    def __init__(self, session: requests.Session, use_browser: bool = False):
        self.session = session
        self.use_browser = use_browser

    def extract_content(self, url: str) -> Optional[ScrapedItem]:
        """Extract content using multiple strategies"""
        logger.debug(f"Extracting content from: {url}")

        # Strategy 1: Try requests first (faster)
        request_worked = False
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                # Check if we got meaningful HTML content
                content_size = len(response.content)
                if content_size < 1000:
                    logger.debug(f"Small content size ({content_size} bytes), likely SPA - will try browser mode")
                elif not self._is_valid_html(response.content):
                    logger.debug(f"Invalid or minimal HTML content - will try browser mode")
                else:
                    request_worked = True

                    item = self._extract_with_trafilatura(url, response.content)
                    if item and len(item.content.strip()) > 200:
                        logger.debug(f"Success with trafilatura: {item.title}")
                        return item

                    # Fallback to BeautifulSoup
                    item = self._extract_with_beautifulsoup(url, response.content)
                    if item and len(item.content.strip()) > 200:
                        logger.debug(f"Success with BeautifulSoup: {item.title}")
                        return item

                    # Fallback to readability
                    item = self._extract_with_readability(url, response.content)
                    if item and len(item.content.strip()) > 200:
                        logger.debug(f"Success with readability: {item.title}")
                        return item

        except requests.RequestException as exc:
            logger.warning(f"Request failed for {url}: {exc}")

        # Strategy 2: Try browser rendering if requests failed or returned minimal content
        if self.use_browser or not request_worked:
            try:
                logger.debug(f"Trying browser rendering for: {url}")
                render_result = sync_render_page(url)
                if render_result.get('html') and not render_result.get('error'):
                    item = self._extract_with_trafilatura(url, render_result['html'].encode())
                    if item and len(item.content.strip()) > 200:
                        logger.debug(f"Success with browser + trafilatura: {item.title}")
                        return item

                    item = self._extract_with_beautifulsoup(url, render_result['html'].encode())
                    if item and len(item.content.strip()) > 200:
                        logger.debug(f"Success with browser + BeautifulSoup: {item.title}")
                        return item

            except Exception as exc:
                logger.warning(f"Browser rendering failed for {url}: {exc}")

        logger.debug(f"All extraction methods failed for: {url}")
        return None

    def _is_valid_html(self, content: Union[str, bytes]) -> bool:
        """Check if content appears to be valid, substantial HTML"""
        try:
            if isinstance(content, bytes):
                content_str = content.decode('utf-8', errors='ignore')
            else:
                content_str = content

            # Basic checks for meaningful HTML content
            content_lower = content_str.lower()

            # Must have basic HTML structure
            if not ('<html' in content_lower or '<body' in content_lower):
                return False

            # Should have some actual content elements
            content_indicators = ['<p', '<div', '<article', '<main', '<section', '<h1', '<h2', '<h3']
            content_count = sum(1 for indicator in content_indicators if indicator in content_lower)

            # Should have more than just scripts
            script_count = content_lower.count('<script')

            # If it's mostly scripts and little content, it's probably an SPA
            return content_count > 3 and (content_count > script_count / 2)

        except Exception:
            return False

    def _extract_with_trafilatura(self, url: str, content: Union[str, bytes]) -> Optional[ScrapedItem]:
        """Extract using trafilatura"""
        try:
            extracted_content = trafilatura.extract(
                content,
                output_format='markdown',
                include_comments=False,
                include_tables=True,
                include_links=True,
                favor_precision=True
            )

            if not extracted_content or len(extracted_content.strip()) < 100:
                return None

            # Get title from trafilatura metadata
            metadata = trafilatura.extract_metadata(content)
            title = self._get_title_from_metadata(metadata, extracted_content)

            return ScrapedItem(
                title=title,
                content=extracted_content,
                content_type=self._classify_content(url, title, extracted_content),
                source_url=url
            )

        except Exception as exc:
            logger.debug(f"Trafilatura extraction failed for {url}: {exc}")
            return None

    def _extract_with_beautifulsoup(self, url: str, content: Union[str, bytes]) -> Optional[ScrapedItem]:
        """Extract using BeautifulSoup with smart content detection"""
        try:
            soup = BeautifulSoup(content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()

            # Try to find main content area
            main_content = self._find_main_content(soup)
            if not main_content:
                return None

            # Extract text and convert to markdown-like format
            text_content = self._html_to_markdown(main_content)

            if len(text_content.strip()) < 100:
                return None

            # Extract title
            title = self._extract_title_from_soup(soup)

            return ScrapedItem(
                title=title,
                content=text_content,
                content_type=self._classify_content(url, title, text_content),
                source_url=url
            )

        except Exception as exc:
            logger.debug(f"BeautifulSoup extraction failed for {url}: {exc}")
            return None

    def _extract_with_readability(self, url: str, content: Union[str, bytes]) -> Optional[ScrapedItem]:
        """Extract using python-readability"""
        try:
            # Convert bytes to string if needed
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')

            doc = Document(content)
            readable_html = doc.summary()
            title = doc.title()

            if not readable_html:
                return None

            # Convert to text
            soup = BeautifulSoup(readable_html, 'html.parser')
            text_content = self._html_to_markdown(soup)

            if len(text_content.strip()) < 100:
                return None

            return ScrapedItem(
                title=title or "Untitled",
                content=text_content,
                content_type=self._classify_content(url, title or "", text_content),
                source_url=url
            )

        except Exception as exc:
            logger.debug(f"Readability extraction failed for {url}: {exc}")
            return None

    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the main content area using various strategies"""
        # Strategy 1: Look for semantic HTML5 elements
        for tag in ['main', 'article']:
            element = soup.find(tag)
            if element:
                return element

        # Strategy 2: Look for common content class/id patterns
        content_selectors = [
            '[role="main"]',
            '.post-content',
            '.article-content', 
            '.blog-content',
            '.entry-content',
            '.post-body',
            '.blog-post',
            '.article-body',
            '.content-body',
            '.main-content',
            '.content',
            '#content',
            '#main'
        ]

        for selector in content_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    return element
            except Exception:
                continue

        # Strategy 3: Find content by excluding navigation/header/footer
        # Remove navigation, header, footer, sidebar elements first
        for unwanted in soup(['nav', 'header', 'footer', 'aside']):
            unwanted.decompose()
        
        # Also remove elements with navigation-like classes
        nav_classes = ['.navigation', '.navbar', '.menu', '.sidebar', '.footer', '.header']
        for nav_class in nav_classes:
            for element in soup.select(nav_class):
                element.decompose()
        
        # Strategy 4: Find the largest meaningful text block after cleanup
        text_elements = soup.find_all(['div', 'section', 'p'], string=False)
        if text_elements:
            # Filter out elements that are likely not content
            filtered_elements = []
            for elem in text_elements:
                text = elem.get_text().strip()
                # Skip very short elements or those with mainly links
                if len(text) > 100:
                    link_density = len(elem.find_all('a')) / max(1, len(text.split()))
                    if link_density < 0.3:  # Less than 30% links
                        filtered_elements.append((elem, len(text)))
            
            if filtered_elements:
                # Sort by text length and return the largest
                filtered_elements.sort(key=lambda x: x[1], reverse=True)
                return filtered_elements[0][0]

        return None

    def _html_to_markdown(self, element: BeautifulSoup) -> str:
        """Convert HTML to markdown-like text"""
        if not element:
            return ""

        # Handle headers
        for i in range(1, 7):
            for header in element.find_all(f'h{i}'):
                header.string = f"{'#' * i} {header.get_text()}\n\n"

        # Handle paragraphs
        for p in element.find_all('p'):
            if p.string:
                p.string = f"{p.get_text()}\n\n"

        # Handle lists
        for ul in element.find_all(['ul', 'ol']):
            items = ul.find_all('li')
            list_text = ""
            for item in items:
                list_text += f"- {item.get_text()}\n"
            if list_text:
                ul.string = f"{list_text}\n"

        # Handle links
        for link in element.find_all('a'):
            href = link.get('href', '')
            text = link.get_text()
            if href and text:
                link.string = f"[{text}]({href})"

        # Handle code blocks
        for code in element.find_all(['code', 'pre']):
            code.string = f"`{code.get_text()}`"

        return element.get_text()

    def _extract_title_from_soup(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML"""
        # Try various title sources
        title_selectors = [
            'h1',
            '.post-title',
            '.article-title',
            '.entry-title',
            'title'
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()

        return "Untitled"

    def _get_title_from_metadata(self, metadata: Dict[str, Any], content: str) -> str:
        """Get title from trafilatura metadata or content"""
        if metadata and metadata.get('title'):
            return metadata['title']

        # Fallback to first heading in content
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        return "Untitled"

    def _classify_content(self, url: str, title: str, content: str) -> str:
        """Enhanced content classification with platform awareness"""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()

        # Platform-specific classification first
        if 'substack.com' in url_lower:
            return 'blog'  # Substack is primarily blogging platform
        elif 'medium.com' in url_lower:
            return 'blog'  # Medium is primarily blogging platform
        elif 'linkedin.com' in url_lower:
            return 'linkedin_post'
        elif 'reddit.com' in url_lower:
            return 'reddit_comment'

        # Content type patterns
        patterns = {
            'podcast_transcript': [
                'podcast', 'episode', 'transcript', 'audio', 'listen'
            ],
            'call_transcript': [
                'transcript', 'interview', 'conversation', 'call', 'recording'
            ],
            'book': [
                'book', 'chapter', 'manual', 'documentation', 'reference'
            ],
            'news': [
                '/news/', 'breaking', 'announcement', 'press-release', 'update'
            ]
        }

        # Check URL and title for specific content types
        for content_type, keywords in patterns.items():
            for keyword in keywords:
                if keyword in url_lower or keyword in title_lower:
                    return content_type

        # Check content for tutorial indicators (be more strict)
        content_words = content_lower.split()
        if len(content_words) > 100:  # Only check content if substantial
            # Strong tutorial indicators
            strong_tutorial_indicators = [
                'step 1', 'step one', 'first step', 'tutorial:', 'how to',
                'walkthrough', 'guide:', 'instructions', 'follow these steps'
            ]
            tutorial_count = sum(1 for indicator in strong_tutorial_indicators if indicator in content_lower)

            # Also check for numbered steps pattern
            numbered_steps = len([word for word in content_words[:200] if word.startswith(('1.', '2.', '3.', '4.', '5.'))])

            if tutorial_count >= 2 or numbered_steps >= 3:
                return 'tutorial'

        # Default to blog for most content
        return 'blog'