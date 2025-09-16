"""
Data models for the OGScraper
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ScrapedItem:
    """Represents a single scraped content item"""
    title: str
    content: str
    content_type: str
    source_url: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "source_url": self.source_url
        }


@dataclass
class ScrapingResult:
    """Represents the complete result of a scraping operation"""
    site: str
    items: List[ScrapedItem]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "site": self.site,
            "items": [item.to_dict() for item in self.items]
        }