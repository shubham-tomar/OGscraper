"""
Content extraction module for fetching and processing web content
"""

import logging
from typing import Optional

import requests
import trafilatura
from bs4 import BeautifulSoup

from .models import ScrapedItem


logger = logging.getLogger(__name__)


class ContentExtractor:
    """Handles content extraction from web pages"""

    def __init__(self, session: requests.Session):
        self.session = session

    def fetch_and_extract(self, url: str) -> Optional[ScrapedItem]:
        """Fetch URL and extract content"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return None

            # Extract content with trafilatura
            content = trafilatura.extract(
                response.content,
                output_format='markdown',
                include_comments=False,
                include_tables=True,
                include_links=True
            )

            if not content or len(content.strip()) < 100:
                logger.debug(f"Insufficient content extracted from {url}")
                return None

            # Extract title
            title = self._extract_title(response.content, content)

            # Classify content type
            content_type = self._classify_content(url, title, content)

            return ScrapedItem(
                title=title,
                content=content,
                content_type=content_type,
                source_url=url
            )

        except requests.RequestException as exc:
            logger.warning(f"Request failed for {url}: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Unexpected error extracting content from {url}: {exc}")
            return None

    def _extract_title(self, html_content: bytes, markdown_content: str) -> str:
        """Extract title from HTML or markdown content"""
        try:
            # Try to get title from HTML first
            soup = BeautifulSoup(html_content, 'html.parser')
            title_tag = soup.find('title')
            if title_tag and title_tag.text.strip():
                return title_tag.text.strip()
        except Exception:
            pass

        # Fallback to markdown content
        return self._extract_title_from_markdown(markdown_content)

    def _extract_title_from_markdown(self, content: str) -> str:
        """Extract title from markdown content"""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        return "Untitled"

    def _classify_content(self, url: str, title: str, content: str) -> str:
        """Classify content type based on URL, title, and content"""
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()

        # Check for specific content types
        if 'podcast' in url_lower or 'podcast' in title_lower:
            return 'podcast_transcript'
        elif 'transcript' in url_lower or 'transcript' in title_lower or 'transcript' in content_lower:
            return 'call_transcript'
        elif 'linkedin.com' in url_lower:
            return 'linkedin_post'
        elif 'reddit.com' in url_lower:
            return 'reddit_comment'
        elif any(word in title_lower for word in ['book', 'chapter', 'guide']):
            return 'book'
        else:
            return 'blog'