"""
Main scraper orchestrator that coordinates all components
"""

import logging
from typing import List

import requests

from .models import ScrapedItem, ScrapingResult
from .discovery import URLDiscoverer
from .extraction import ContentExtractor
from .extractors import MultiExtractor
from .async_extractors import extract_content_parallel_sync
from .processing import ContentProcessor


logger = logging.getLogger(__name__)


class WebScraper:
    """Main scraper class that orchestrates the scraping process"""

    def __init__(self, base_url: str, chunk_size: int = 8000, use_browser: bool = False,
                 parallel: bool = True, max_concurrent: int = 10):
        self.base_url = base_url
        self.chunk_size = chunk_size
        self.use_browser = use_browser
        self.parallel = parallel
        self.max_concurrent = max_concurrent

        # Setup HTTP session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Initialize components
        self.discoverer = URLDiscoverer(base_url, self.session, use_browser)
        self.extractor = MultiExtractor(self.session, use_browser)
        self.processor = ContentProcessor(chunk_size)

    def scrape(self, max_items: int = 100) -> ScrapingResult:
        """Main scraping method that coordinates all components"""
        logger.info(f"Starting scrape of {self.base_url}")

        # Check if base_url is a specific page (contains path) vs domain
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        is_specific_url = bool(parsed.path and parsed.path != '/' and not parsed.path.endswith('/'))
        
        if is_specific_url:
            # For specific URLs, just extract that page directly
            logger.info(f"Direct URL provided: {self.base_url}")
            urls = [self.base_url]
        else:
            # Step 1: Discover URLs for domain-level scraping
            logger.info("Discovering URLs...")
            urls = self.discoverer.discover_urls()
            logger.info(f"Found {len(urls)} URLs to process")

        if not urls:
            logger.warning("No URLs discovered. The site might not have discoverable content.")
            return ScrapingResult(site=self.base_url, items=[])

        # Step 2: Extract content from URLs
        logger.info("Extracting content...")
        if self.parallel:
            items = self._extract_content_parallel(urls, max_items)
        else:
            items = self._extract_content_sequential(urls, max_items)
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

    def _extract_content_sequential(self, urls: List[str], max_items: int) -> List[ScrapedItem]:
        """Extract content from URLs sequentially (slow but compatible)"""
        items = []
        processed = 0

        for i, url in enumerate(urls):
            if processed >= max_items:
                logger.info(f"Reached max items limit ({max_items})")
                break

            logger.debug(f"Processing {i + 1}/{min(len(urls), max_items)}: {url}")

            try:
                item = self.extractor.extract_content(url)
                if item:
                    items.append(item)
                    processed += 1
                    logger.debug(f"Successfully extracted: {item.title}")
                else:
                    logger.debug(f"No content extracted from: {url}")

            except Exception as exc:
                logger.error(f"Error processing {url}: {exc}")
                continue

        return items

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()