"""
Content processing module for chunking, deduplication, and enrichment
"""

import hashlib
import logging
from typing import List

from .models import ScrapedItem


logger = logging.getLogger(__name__)


class ContentProcessor:
    """Handles post-processing of scraped content"""

    def __init__(self, max_chunk_size: int = 8000):
        self.max_chunk_size = max_chunk_size

    def process_items(self, items: List[ScrapedItem]) -> List[ScrapedItem]:
        """Process items through deduplication and chunking"""
        # Remove duplicates first
        unique_items = self._deduplicate_items(items)
        logger.info(f"After deduplication: {len(unique_items)} items (was {len(items)})")

        # Then chunk large items
        chunked_items = self._chunk_large_items(unique_items)
        logger.info(f"After chunking: {len(chunked_items)} items")

        return chunked_items

    def _deduplicate_items(self, items: List[ScrapedItem]) -> List[ScrapedItem]:
        """Remove duplicate items based on content hash"""
        seen_hashes = set()
        unique_items = []

        # Check if we have many items with the same generic content (likely extraction failures)
        content_hash_counts = {}
        for item in items:
            content_hash = self._generate_content_hash(item.content)
            content_hash_counts[content_hash] = content_hash_counts.get(content_hash, 0) + 1

        # If we have many duplicates of the same content, it's likely a generic page
        generic_extraction_detected = False
        template_content_hash = None
        for content_hash, count in content_hash_counts.items():
            if count > 3:  # If more than 3 items have identical content
                logger.warning(f"Detected {count} items with identical content - likely generic page extraction failure")
                generic_extraction_detected = True
                template_content_hash = content_hash

        # If we detected generic extraction failure, filter out template content entirely
        if generic_extraction_detected and template_content_hash:
            logger.warning("Filtering out template/homepage content served on blog URLs")
            filtered_items = []
            for item in items:
                item_hash = self._generate_content_hash(item.content)
                if item_hash != template_content_hash:
                    filtered_items.append(item)
                else:
                    # Check if this might be a valid homepage vs a blog post serving template content
                    if self._is_likely_blog_url(item.source_url):
                        logger.warning(f"Skipping template content on blog URL: {item.source_url}")
                    else:
                        # Keep homepage/main content if it's from the main domain
                        filtered_items.append(item)
                        logger.debug(f"Keeping homepage content: {item.source_url}")
            
            # If we filtered everything out, return one representative item
            if not filtered_items and items:
                logger.warning("All items were template content, keeping one representative")
                representative = items[0]
                representative.title = f"[Template Content] {representative.title}"
                return [representative]
            
            items = filtered_items

        # Normal content-based deduplication
        for item in items:
            content_hash = self._generate_content_hash(item.content)

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_items.append(item)
            else:
                logger.warning(f"Duplicate content found: {item.title} (URL: {item.source_url}) - Content length: {len(item.content)}")

        return unique_items

    def _generate_content_hash(self, content: str) -> str:
        """Generate MD5 hash of content for deduplication"""
        return hashlib.md5(content.encode()).hexdigest()

    def _chunk_large_items(self, items: List[ScrapedItem]) -> List[ScrapedItem]:
        """Split large content items into smaller chunks"""
        processed_items = []

        for item in items:
            # Be more conservative with chunking - only chunk very large content
            # and avoid chunking if it would create too many small pieces
            if len(item.content) > self.max_chunk_size * 1.5:  # 12k chars default
                chunks = self._chunk_content(item.content)

                # Only chunk if we get reasonable-sized pieces
                if len(chunks) <= 3 and all(len(chunk) > 1000 for chunk in chunks):
                    for i, chunk in enumerate(chunks):
                        chunk_item = ScrapedItem(
                            title=f"{item.title} (Part {i+1})" if len(chunks) > 1 else item.title,
                            content=chunk,
                            content_type=item.content_type,
                            source_url=item.source_url
                        )
                        processed_items.append(chunk_item)
                    logger.debug(f"Split '{item.title}' into {len(chunks)} chunks")
                else:
                    # Keep original if chunking would create poor results
                    processed_items.append(item)
                    logger.debug(f"Kept '{item.title}' intact (chunking would create poor results)")
            else:
                processed_items.append(item)

        return processed_items

    def _chunk_content(self, content: str) -> List[str]:
        """Split content into chunks at paragraph boundaries"""
        chunks = []
        paragraphs = content.split('\n\n')
        current_chunk = []
        current_length = 0

        for paragraph in paragraphs:
            paragraph_length = len(paragraph)

            # If adding this paragraph would exceed max size and we have content
            if current_length + paragraph_length > self.max_chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_length = paragraph_length
            else:
                current_chunk.append(paragraph)
                current_length += paragraph_length + 2  # +2 for \n\n

        # Add the last chunk if it has content
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks if chunks else [content]  # Fallback to original content
    
    def _is_likely_blog_url(self, url: str) -> bool:
        """Check if URL pattern suggests it should contain unique blog content"""
        blog_indicators = ['/blog/', '/blogs/', '/article/', '/articles/', '/post/', '/posts/', 
                          '/news/', '/resource/', '/resources/', '/insights/', '/updates/',
                          '/content/', '/press/', '/media/', '/stories/']
        return any(indicator in url.lower() for indicator in blog_indicators)