"""
OGScraper - Universal web scraper for technical content extraction
"""

__version__ = "0.1.0"
__author__ = "OGScraper Team"

from .models import ScrapedItem, ScrapingResult
from .scraper import WebScraper

__all__ = ["ScrapedItem", "ScrapingResult", "WebScraper"]