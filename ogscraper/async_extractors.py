"""
Async content extraction with parallel processing for high performance
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor
import time

import aiohttp
import trafilatura
from bs4 import BeautifulSoup
from readability.readability import Document

from .models import ScrapedItem
from .renderer import PlaywrightRenderer


logger = logging.getLogger(__name__)


class AsyncMultiExtractor:
    """High-performance async content extractor with parallel processing"""

    def __init__(self, use_browser: bool = False, max_concurrent: int = 10, timeout: int = 15):
        self.use_browser = use_browser
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.session = None
        self.browser_renderer = None

    async def __aenter__(self):
        """Async context manager entry"""
        # Create aiohttp session
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )

        # Initialize browser renderer if needed
        if self.use_browser:
            self.browser_renderer = PlaywrightRenderer()
            await self.browser_renderer.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

        if self.browser_renderer:
            await self.browser_renderer.__aexit__(exc_type, exc_val, exc_tb)

    async def extract_content_parallel(self, urls: List[str]) -> List[Optional[ScrapedItem]]:
        """Extract content from multiple URLs in parallel"""
        logger.info(f"Starting parallel extraction of {len(urls)} URLs with max_concurrent={self.max_concurrent}")
        start_time = time.time()

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # Create tasks for parallel processing
        tasks = [
            self._extract_single_with_semaphore(semaphore, url, i)
            for i, url in enumerate(urls)
        ]

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and None results
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Exception extracting {urls[i]}: {result}")
            elif result is not None:
                valid_results.append(result)

        duration = time.time() - start_time
        logger.info(f"Parallel extraction completed in {duration:.1f}s: {len(valid_results)}/{len(urls)} successful")

        return valid_results

    async def _extract_single_with_semaphore(self, semaphore: asyncio.Semaphore, url: str, index: int) -> Optional[ScrapedItem]:
        """Extract content from a single URL with semaphore limiting"""
        async with semaphore:
            logger.debug(f"[{index}] Processing: {url}")
            start_time = time.time()

            try:
                result = await self._extract_content_async(url)
                duration = time.time() - start_time

                if result:
                    logger.debug(f"[{index}] ✅ Success ({duration:.1f}s): {result.title[:50]}...")
                else:
                    logger.debug(f"[{index}] ❌ Failed ({duration:.1f}s): {url}")

                return result

            except Exception as exc:
                duration = time.time() - start_time
                logger.warning(f"[{index}] ⚠️ Error ({duration:.1f}s): {url} - {exc}")
                return None

    async def _extract_content_async(self, url: str) -> Optional[ScrapedItem]:
        """Async content extraction with fallback strategies"""
        # Strategy 1: Try HTTP request first (fastest)
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    content_size = len(content)

                    # Only flag as invalid if content is genuinely minimal (like SPAs)
                    if content_size < 1000:
                        logger.debug(f"Small content ({content_size} bytes) - will try browser mode")
                    elif not self._is_valid_html(content):
                        logger.debug(f"Invalid HTML content - will try browser mode")
                    else:
                        # Try extraction with the fetched content
                        item = await self._extract_with_methods(url, content)
                        if item and len(item.content.strip()) > 200:
                            return item

        except Exception as exc:
            logger.debug(f"HTTP request failed for {url}: {exc}")

        # Strategy 2: Browser rendering if needed
        if self.use_browser and self.browser_renderer:
            try:
                render_result = await self.browser_renderer.render_page(url)
                if render_result.get('html') and not render_result.get('error'):
                    html_content = render_result['html'].encode()
                    item = await self._extract_with_methods(url, html_content)
                    if item and len(item.content.strip()) > 200:
                        return item
            except Exception as exc:
                logger.debug(f"Browser rendering failed for {url}: {exc}")

        return None

    async def _extract_with_methods(self, url: str, content: bytes) -> Optional[ScrapedItem]:
        """Try different extraction methods with thread pool for CPU-bound operations"""
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=3) as executor:
            # Run extraction methods in parallel in thread pool
            tasks = [
                loop.run_in_executor(executor, self._extract_with_trafilatura, url, content),
                loop.run_in_executor(executor, self._extract_with_beautifulsoup, url, content),
                loop.run_in_executor(executor, self._extract_with_readability, url, content)
            ]

            # Wait for the first successful result
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    if result and len(result.content.strip()) > 200:
                        # Cancel remaining tasks
                        for t in tasks:
                            if not t.done():
                                t.cancel()
                        return result
                except Exception as exc:
                    logger.debug(f"Extraction method failed: {exc}")
                    continue

        return None

    def _extract_with_trafilatura(self, url: str, content: bytes) -> Optional[ScrapedItem]:
        """Extract using trafilatura (CPU-bound, runs in thread pool)"""
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
            try:
                metadata = trafilatura.extract_metadata(content)
                title = self._get_title_from_metadata(metadata, extracted_content)
            except Exception:
                title = self._extract_title_from_content(extracted_content)

            return ScrapedItem(
                title=title,
                content=extracted_content,
                content_type=self._classify_content(url, title, extracted_content),
                source_url=url
            )

        except Exception as exc:
            logger.debug(f"Trafilatura extraction failed for {url}: {exc}")
            return None

    def _extract_with_beautifulsoup(self, url: str, content: bytes) -> Optional[ScrapedItem]:
        """Extract using BeautifulSoup (CPU-bound, runs in thread pool)"""
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

    def _extract_with_readability(self, url: str, content: bytes) -> Optional[ScrapedItem]:
        """Extract using readability (CPU-bound, runs in thread pool)"""
        try:
            content_str = content.decode('utf-8', errors='ignore')
            doc = Document(content_str)
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

    def _is_valid_html(self, content: bytes) -> bool:
        """Check if content appears to be valid, substantial HTML"""
        try:
            content_str = content.decode('utf-8', errors='ignore')
            content_lower = content_str.lower()

            # Must have basic HTML structure
            if not ('<html' in content_lower or '<body' in content_lower):
                return False

            # Should have some actual content elements
            content_indicators = ['<p', '<div', '<article', '<main', '<section', '<h1', '<h2', '<h3']
            content_count = sum(1 for indicator in content_indicators if indicator in content_lower)

            # Should have more than just scripts
            script_count = content_lower.count('<script')

            # More lenient validation - if there's reasonable content, consider it valid
            # Even if script count is high, as long as there's substantial content
            return content_count >= 2 and (script_count == 0 or content_count >= 1)

        except Exception:
            return False

    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the main content area using various strategies"""
        # Strategy 1: Look for semantic HTML5 elements
        for tag in ['main', 'article']:
            element = soup.find(tag)
            if element:
                return element

        # Strategy 2: Look for common content class/id patterns
        content_selectors = [
            '[role="main"]', '.content', '.main-content', '.post-content',
            '.article-content', '.blog-content', '#content', '#main',
            '.entry-content', '.post-body'
        ]

        for selector in content_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    return element
            except Exception:
                continue

        # Strategy 3: Find the largest text block
        text_elements = soup.find_all(['div', 'section'], string=False)
        if text_elements:
            text_elements.sort(key=lambda x: len(x.get_text()), reverse=True)
            if text_elements and len(text_elements[0].get_text()) > 200:
                return text_elements[0]

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
        title_selectors = ['h1', '.post-title', '.article-title', '.entry-title', 'title']

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()

        return "Untitled"

    def _get_title_from_metadata(self, metadata: Dict[str, Any], content: str) -> str:
        """Get title from trafilatura metadata or content"""
        if metadata and metadata.get('title'):
            return metadata['title']

        return self._extract_title_from_content(content)

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from markdown content"""
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
            return 'blog'
        elif 'medium.com' in url_lower:
            return 'blog'
        elif 'linkedin.com' in url_lower:
            return 'linkedin_post'
        elif 'reddit.com' in url_lower:
            return 'reddit_comment'

        # Content type patterns
        patterns = {
            'podcast_transcript': ['podcast', 'episode', 'transcript', 'audio', 'listen'],
            'call_transcript': ['transcript', 'interview', 'conversation', 'call', 'recording'],
            'book': ['book', 'chapter', 'manual', 'documentation', 'reference'],
            'news': ['/news/', 'breaking', 'announcement', 'press-release', 'update']
        }

        # Check URL and title for specific content types
        for content_type, keywords in patterns.items():
            for keyword in keywords:
                if keyword in url_lower or keyword in title_lower:
                    return content_type

        # Check content for tutorial indicators (be more strict)
        content_words = content_lower.split()
        if len(content_words) > 100:
            strong_tutorial_indicators = [
                'step 1', 'step one', 'first step', 'tutorial:', 'how to',
                'walkthrough', 'guide:', 'instructions', 'follow these steps'
            ]
            tutorial_count = sum(1 for indicator in strong_tutorial_indicators if indicator in content_lower)

            # Also check for numbered steps pattern
            numbered_steps = len([word for word in content_words[:200] if word.startswith(('1.', '2.', '3.', '4.', '5.'))])

            if tutorial_count >= 2 or numbered_steps >= 3:
                return 'tutorial'

        return 'blog'


# Synchronous wrapper for backward compatibility
def extract_content_parallel_sync(urls: List[str], use_browser: bool = False, max_concurrent: int = 10) -> List[Optional[ScrapedItem]]:
    """Synchronous wrapper for parallel extraction"""
    async def _extract():
        async with AsyncMultiExtractor(use_browser=use_browser, max_concurrent=max_concurrent) as extractor:
            return await extractor.extract_content_parallel(urls)

    return asyncio.run(_extract())