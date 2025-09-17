"""
Main scraper orchestrator that coordinates all components
"""

import logging
from typing import List

import requests

from .models import ScrapedItem, ScrapingResult
from .discovery import URLDiscoverer
from .async_extractors import extract_content_parallel_sync
from .processing import ContentProcessor


logger = logging.getLogger(__name__)


class WebScraper:
    """Main scraper class that orchestrates the scraping process"""

    def __init__(self, base_url: str, chunk_size: int = 8000, use_browser: bool = False,
                 max_concurrent: int = 15):
        self.base_url = base_url
        self.chunk_size = chunk_size
        self.use_browser = use_browser
        self.max_concurrent = max_concurrent

        # Setup HTTP session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Initialize components
        self.discoverer = URLDiscoverer(base_url, self.session, use_browser)
        self.processor = ContentProcessor(chunk_size)

    def scrape(self, max_items: int = 100) -> ScrapingResult:
        """Main scraping method that coordinates all components"""
        logger.info(f"Starting scrape of {self.base_url}")

        # Check if base_url is a specific page vs blog section/domain
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)

        # Identify blog sections that should use URL discovery
        blog_section_paths = ['/blog', '/blogs', '/articles', '/posts', '/news', '/resource', '/resources']
        is_blog_section = any(parsed.path.rstrip('/').lower() == path for path in blog_section_paths)

        # Only treat as direct URL if it has a specific path that's not a blog section
        is_specific_url = (parsed.path and
                          parsed.path != '/' and
                          not parsed.path.endswith('/') and
                          not is_blog_section)

        if is_specific_url:
            # For specific URLs, just extract that page directly
            logger.info(f"Direct URL provided: {self.base_url}")
            urls = [self.base_url]
        else:
            # Step 1: Discover URLs for domain-level or blog section scraping
            if is_blog_section:
                logger.info(f"Blog section detected: {self.base_url}")
            logger.info("Discovering URLs...")
            urls = self.discoverer.discover_urls()
            logger.info(f"Found {len(urls)} URLs to process")

        if not urls:
            logger.warning("No URLs discovered. The site might not have discoverable content.")
            return ScrapingResult(site=self.base_url, items=[])

        # Step 2: Extract content from URLs (always parallel for speed)
        logger.info("Extracting content...")
        items = self._extract_content_parallel(urls, max_items)
        logger.info(f"Successfully extracted {len(items)} items")

        if not items:
            logger.warning("No content could be extracted from discovered URLs.")
            return ScrapingResult(site=self.base_url, items=[])

        # Step 3: Process content (dedupe and chunk)
        logger.info("Processing content...")
        processed_items = self.processor.process_items(items)

        logger.info(f"Scraping completed. Final count: {len(processed_items)} items")
        return ScrapingResult(site=self.base_url, items=processed_items)

    def _extract_content_parallel(self, urls: List[str], max_items: int) -> List[ScrapedItem]:
        """Extract content from URLs in parallel (fast)"""
        # Limit URLs to max_items
        urls_to_process = urls[:max_items]

        logger.info(f"Using parallel extraction with {self.max_concurrent} concurrent connections")

        # Use the new async parallel extractor
        items = extract_content_parallel_sync(
            urls_to_process,
            use_browser=self.use_browser,
            max_concurrent=self.max_concurrent
        )

        # Filter out None results
        valid_items = [item for item in items if item is not None]
        return valid_items


    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()