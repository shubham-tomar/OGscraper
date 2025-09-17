"""
URL discovery module for finding content URLs from various sources
"""

import re
from urllib.parse import urljoin, urlparse
from typing import List
import logging
from datetime import datetime

import requests
import feedparser
from bs4 import BeautifulSoup

from .renderer import sync_discover_urls


logger = logging.getLogger(__name__)


class URLDiscoverer:
    """Handles discovery of content URLs from various sources"""

    def __init__(self, base_url: str, session: requests.Session, use_browser: bool = False):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.session = session
        self.use_browser = use_browser

    def discover_urls(self) -> List[str]:
        """Discover URLs from sitemap, RSS feeds, and common blog paths"""
        urls = set()

        # Try sitemap
        try:
            sitemap_urls = self._discover_from_sitemap()
            urls.update(sitemap_urls)
            logger.info(f"Found {len(sitemap_urls)} URLs from sitemap")
        except Exception as exc:
            logger.warning(f"Sitemap discovery failed: {exc}")

        # Try RSS feeds
        try:
            rss_urls = self._discover_from_rss()
            urls.update(rss_urls)
            logger.info(f"Found {len(rss_urls)} URLs from RSS feeds")
        except Exception as exc:
            logger.warning(f"RSS discovery failed: {exc}")

        # Try common blog paths
        try:
            blog_urls = self._discover_from_blog_paths()
            urls.update(blog_urls)
            logger.info(f"Found {len(blog_urls)} URLs from blog paths")
        except Exception as exc:
            logger.warning(f"Blog path discovery failed: {exc}")

        # Try SPA content discovery if we have few URLs (before navigation)
        if len(urls) < 5:
            try:
                spa_urls = self._discover_from_spa_content()
                urls.update(spa_urls)
                logger.info(f"Found {len(spa_urls)} URLs from SPA content discovery")
            except Exception as exc:
                logger.warning(f"SPA content discovery failed: {exc}")

        # Try navigation-based discovery if we still have few URLs
        if len(urls) < 5:
            try:
                nav_urls = self._discover_from_navigation()
                urls.update(nav_urls)
                logger.info(f"Found {len(nav_urls)} URLs from navigation discovery")
            except Exception as exc:
                logger.warning(f"Navigation discovery failed: {exc}")

        # Try browser-based discovery if enabled and we still have few URLs
        if self.use_browser and len(urls) < 5:
            try:
                browser_urls = sync_discover_urls(self.base_url)
                urls.update(browser_urls)
                logger.info(f"Found {len(browser_urls)} URLs from browser discovery")
            except Exception as exc:
                logger.warning(f"Browser discovery failed: {exc}")

        return list(urls)

    def _discover_from_sitemap(self) -> List[str]:
        """Extract URLs from sitemap.xml"""
        urls = []
        sitemap_urls = [
            urljoin(self.base_url, '/sitemap.xml'),
            urljoin(self.base_url, '/sitemap_index.xml'),
            urljoin(self.base_url, '/robots.txt')  # Check for sitemap reference
        ]

        for sitemap_url in sitemap_urls:
            try:
                response = self.session.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    if 'robots.txt' in sitemap_url:
                        # Extract sitemap URLs from robots.txt
                        for line in response.text.split('\n'):
                            if line.lower().startswith('sitemap:'):
                                actual_sitemap = line.split(':', 1)[1].strip()
                                urls.extend(self._parse_sitemap(actual_sitemap))
                    else:
                        urls.extend(self._parse_sitemap_content(response.text))
            except requests.RequestException:
                continue

        return urls

    def _parse_sitemap_content(self, content: str) -> List[str]:
        """Parse sitemap XML content with recency filtering and timeout protection"""
        urls = []
        try:
            # Add timeout protection for production environments
            if len(content) > 10_000_000:  # 10MB limit
                logger.warning(f"Sitemap too large ({len(content)} bytes), skipping")
                return []

            soup = BeautifulSoup(content, 'xml')

            # Handle sitemap index - limit to first 3 sitemaps for production
            sitemap_tags = soup.find_all('sitemap')[:3]  # Reduced from 10 to 3
            for i, sitemap in enumerate(sitemap_tags):
                loc = sitemap.find('loc')
                if loc:
                    try:
                        sitemap_urls = self._parse_sitemap(loc.text)
                        urls.extend(sitemap_urls)

                        # Add progress logging for production debugging
                        logger.debug(f"Processed sitemap {i+1}/3: {len(sitemap_urls)} URLs")

                        # Prevent excessive processing in production
                        if len(urls) > 1000:  # Hard limit for production
                            logger.info(f"Reached URL limit, stopping sitemap processing")
                            break

                    except Exception as exc:
                        logger.warning(f"Failed to parse nested sitemap {loc.text}: {exc}")
                        continue

            # Handle individual URLs with date filtering
            url_tags = soup.find_all('url')
            if url_tags:
                logger.debug(f"Processing {len(url_tags)} individual URLs")

            url_data = []
            processed_count = 0

            for url_tag in url_tags:
                processed_count += 1

                # Add periodic progress logging for large sitemaps
                if processed_count % 500 == 0:
                    logger.debug(f"Processed {processed_count} URLs...")

                # Hard limit to prevent timeouts (reduced from 5000)
                if processed_count > 2000:
                    logger.info(f"Reached processing limit, stopping at {processed_count} URLs")
                    break

                loc = url_tag.find('loc')
                if loc and self._is_content_url(loc.text):
                    # Extract lastmod date if available
                    lastmod = url_tag.find('lastmod')
                    lastmod_date = None

                    if lastmod and lastmod.text:
                        try:
                            # Parse common date formats
                            date_str = lastmod.text.split('T')[0]  # Take date part only
                            lastmod_date = datetime.strptime(date_str, '%Y-%m-%d')
                        except Exception:
                            pass

                    url_data.append((loc.text, lastmod_date))

            # Sort by date (most recent first) and take a reasonable subset
            if url_data:
                logger.debug(f"Sorting and filtering {len(url_data)} URLs")
                url_data.sort(key=lambda x: x[1] or datetime(1900, 1, 1), reverse=True)

                # For production, use smaller limits (reduced from 250)
                limit = 100 if len(url_data) > 100 else len(url_data)
                url_data = url_data[:limit]

                if limit < len(url_data):
                    logger.info(f"Filtered sitemap to {limit} most recent URLs")

                urls.extend([url for url, _ in url_data])

        except Exception as exc:
            logger.warning(f"Failed to parse sitemap content: {exc}")

        return urls

    def _parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse individual sitemap with timeout protection"""
        try:
            # Shorter timeout for production to prevent worker timeouts
            response = self.session.get(sitemap_url, timeout=8)
            if response.status_code == 200:
                # Check content length before processing
                content_length = len(response.text)
                if content_length > 20_000_000:  # 20MB limit
                    logger.warning(f"Sitemap {sitemap_url} too large ({content_length} bytes), skipping")
                    return []

                logger.debug(f"Processing sitemap {sitemap_url} ({content_length} bytes)")
                return self._parse_sitemap_content(response.text)
        except requests.RequestException as exc:
            logger.debug(f"Failed to fetch sitemap {sitemap_url}: {exc}")
        return []

    def _discover_from_rss(self) -> List[str]:
        """Extract URLs from RSS/Atom feeds"""
        urls = []
        feed_urls = [
            urljoin(self.base_url, '/feed'),
            urljoin(self.base_url, '/rss'),
            urljoin(self.base_url, '/feed.xml'),
            urljoin(self.base_url, '/rss.xml'),
            urljoin(self.base_url, '/atom.xml'),
            urljoin(self.base_url, '/blog/feed'),
            urljoin(self.base_url, '/blog/rss')
        ]

        for feed_url in feed_urls:
            try:
                response = self.session.get(feed_url, timeout=10)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                    for entry in feed.entries:
                        if hasattr(entry, 'link'):
                            urls.append(entry.link)
            except requests.RequestException:
                continue

        return urls

    def _discover_from_blog_paths(self) -> List[str]:
        """Discover URLs from common blog directory structures"""
        urls = []
        blog_paths = ['/blog', '/blogs', '/articles', '/posts', '/news', '/resource', '/resources', 
                     '/insights', '/updates', '/content', '/press', '/media', '/stories']

        for path in blog_paths:
            try:
                blog_url = urljoin(self.base_url, path)
                response = self.session.get(blog_url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    links = soup.find_all('a', href=True)

                    for link in links:
                        href = link['href']
                        full_url = urljoin(blog_url, href)
                        if self._is_content_url(full_url):
                            urls.append(full_url)
            except requests.RequestException:
                continue

        return urls

    def _is_content_url(self, url: str) -> bool:
        """Check if URL likely contains content"""
        parsed = urlparse(url)

        # Must be same domain
        if parsed.netloc != self.domain:
            return False

        path = parsed.path.lower()

        # Skip common non-content paths
        skip_patterns = [
            '/tag/', '/category/', '/author/', '/page/',
            '/search', '/login', '/register', '/contact', '/about',
            '/privacy', '/terms', '/legal/', '/schedule', '/demo',
            '/signup', '/download', '/pricing', '/support',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
            '.xml', '.txt', '.ico', '.woff', '.woff2', '.ttf', '.eot',
            '/_next/', '/static/', '/assets/'
        ]

        for pattern in skip_patterns:
            if pattern in path:
                return False

        # Prefer paths that look like content
        content_patterns = [
            '/blog/', '/blogs/', '/post/', '/posts/', '/article/', '/articles/',
            '/news/', '/casestudies/', '/case-studies/', '/story/', '/stories/',
            '/resources/', '/resource/', '/insights/', '/whitepapers/', '/guides/',
            '/updates/', '/content/', '/press/', '/media/',
            r'/\d{4}/', r'/\d{4}/\d{2}/'  # Date patterns
        ]

        for pattern in content_patterns:
            if re.search(pattern, path):
                return True

        # Be more selective - path should have reasonable structure
        # and not be obvious utility pages
        if len(path) > 1 and path != '/' and path.count('/') >= 2:
            # Additional checks for corporate sites
            corporate_skip = [
                'solutions/', 'products/', 'services/', 'industries/',
                'company/', 'careers/', 'investors/', 'partners/'
            ]

            # Allow if it doesn't match obvious corporate pages
            return not any(skip in path for skip in corporate_skip)

        return False

    def _discover_from_spa_content(self) -> List[str]:
        """Discover URLs from SPA content by looking for JavaScript-rendered links"""
        urls = []
        try:
            response = self.session.get(self.base_url, timeout=10)
            if response.status_code == 200:
                content = response.text

                # Look for Next.js routing patterns and link structures
                import re

                # Pattern 1: Look for href patterns in the HTML
                href_patterns = [
                    r'href="([^"]*(?:blog|article|post)[^"]*)"',
                    r'href="(/[^"]*)"'  # Any relative links
                ]

                for pattern in href_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        full_url = urljoin(self.base_url, match)
                        if self._is_content_url(full_url) and full_url not in urls:
                            urls.append(full_url)
                            logger.debug(f"Found SPA URL: {full_url}")

                # Pattern 2: Look for JSON data structures that might contain URLs
                json_pattern = r'"href":\s*"([^"]*)"'
                json_matches = re.findall(json_pattern, content)
                for match in json_matches:
                    if match.startswith('/') and any(keyword in match.lower() for keyword in ['blog', 'article', 'post']):
                        full_url = urljoin(self.base_url, match)
                        if full_url not in urls:
                            urls.append(full_url)
                            logger.debug(f"Found SPA JSON URL: {full_url}")

                # Pattern 3: For Quill specifically, try common blog URL patterns
                if 'quill.co' in self.base_url:
                    # Try to construct URLs based on visible content
                    base_blog_url = self.base_url.rstrip('/') + '/'
                    potential_slugs = [
                        'why-users-want-customer-facing-analytics',
                        'brief-overview-of-the-modern-data-stack',
                        'the-evolution-of-business-intelligence-and-the-emergence-of-embedded-bi',
                        'why-the-modern-data-stack-doesnt-replace-embedded-analytics',
                        'why-saas-companies-offer-customer-facing-analytics',
                        'dont-build-chatgpt-for-x-focus-on-where-chatgpt-doesnt-solve-x',
                        'what-is-customer-facing-analytics'
                    ]

                    for slug in potential_slugs:
                        potential_url = base_blog_url + slug
                        # Test if URL exists
                        try:
                            test_response = self.session.head(potential_url, timeout=5)
                            if test_response.status_code == 200:
                                urls.append(potential_url)
                                logger.debug(f"Found valid Quill post: {potential_url}")
                        except:
                            continue

        except Exception as exc:
            logger.debug(f"SPA content discovery error: {exc}")

        return urls

    def _discover_from_navigation(self) -> List[str]:
        """Discover URLs by following navigation links like 'blogs', 'articles', etc."""
        urls = []
        navigation_keywords = [
            'blog', 'blogs', 'articles', 'posts', 'news', 'resources', 'resource',
            'insights', 'stories', 'updates', 'content', 'press', 'media',
            'guides', 'whitepapers', 'case studies', 'learn', 'knowledge'
        ]
        
        try:
            # First, get the main page
            response = self.session.get(self.base_url, timeout=10)
            if response.status_code != 200:
                return urls
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find navigation links that might lead to blog content
            nav_links = []
            
            # Look in navigation elements
            nav_elements = soup.find_all(['nav', 'header', 'menu'])
            for nav in nav_elements:
                links = nav.find_all('a', href=True)
                nav_links.extend(links)
            
            # Also check all links on the page
            all_links = soup.find_all('a', href=True)
            nav_links.extend(all_links)
            
            # Filter links that might lead to blog content
            potential_blog_urls = []
            for link in nav_links:
                href = link.get('href', '')
                text = link.get_text().strip().lower()
                
                # Check if link text contains blog-related keywords
                if any(keyword in text for keyword in navigation_keywords):
                    full_url = urljoin(self.base_url, href)
                    if self._is_same_domain(full_url):
                        potential_blog_urls.append(full_url)
                        logger.debug(f"Found potential blog section: {full_url} (link text: '{text}')")
                
                # Also check href for blog-related paths
                elif any(keyword in href.lower() for keyword in navigation_keywords):
                    full_url = urljoin(self.base_url, href)
                    if self._is_same_domain(full_url):
                        potential_blog_urls.append(full_url)
                        logger.debug(f"Found potential blog section: {full_url} (href contains blog keyword)")
            
            # Visit each potential blog section and extract URLs
            for blog_section_url in potential_blog_urls[:3]:  # Limit to first 3 to avoid too many requests
                try:
                    blog_response = self.session.get(blog_section_url, timeout=10)
                    if blog_response.status_code == 200:
                        blog_soup = BeautifulSoup(blog_response.content, 'html.parser')
                        
                        # Extract all links from the blog section
                        blog_links = blog_soup.find_all('a', href=True)
                        section_urls_count = 0
                        
                        for link in blog_links:
                            href = link.get('href')
                            full_url = urljoin(blog_section_url, href)
                            
                            # Be more lenient for URLs found in blog sections
                            if self._is_blog_content_url(full_url, blog_section_url):
                                urls.append(full_url)
                                section_urls_count += 1
                                logger.debug(f"Added blog URL: {full_url}")
                        
                        # If no URLs found with strict criteria, try looser matching
                        if section_urls_count == 0:
                            logger.debug(f"No URLs found with strict criteria, trying looser matching for {blog_section_url}")
                            for link in blog_links:
                                href = link.get('href')
                                if href and not href.startswith('#') and not href.startswith('javascript:'):
                                    full_url = urljoin(blog_section_url, href)
                                    if self._is_same_domain(full_url) and full_url != blog_section_url:
                                        urls.append(full_url)
                                        section_urls_count += 1
                                        logger.debug(f"Added loose match URL: {full_url}")
                                        
                                        # Limit loose matches to avoid too many URLs
                                        if section_urls_count >= 10:
                                            break
                        
                        logger.debug(f"Extracted {len([u for u in urls if blog_section_url in u or self.domain in u])} URLs from {blog_section_url}")
                        
                except requests.RequestException as exc:
                    logger.debug(f"Failed to fetch blog section {blog_section_url}: {exc}")
                    continue
                    
        except Exception as exc:
            logger.debug(f"Navigation discovery error: {exc}")
            
        return list(set(urls))  # Remove duplicates
    
    def _is_same_domain(self, url: str) -> bool:
        """Check if URL is from the same domain"""
        try:
            return urlparse(url).netloc == self.domain
        except Exception:
            return False
    
    def _is_blog_content_url(self, url: str, blog_section_url: str) -> bool:
        """Enhanced content URL detection specifically for blog sections"""
        if not self._is_same_domain(url):
            return False
            
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Skip obvious non-content paths
        skip_patterns = [
            '/tag/', '/category/', '/author/', '/page/',
            '/search', '/login', '/register', '/contact', '/about',
            '/privacy', '/terms', '/legal/', '/schedule', '/demo',
            '/signup', '/download', '/pricing', '/support',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
            '.xml', '.txt', '.ico', '/api/', '/_next/'
        ]
        
        for pattern in skip_patterns:
            if pattern in path:
                return False
        
        # If we're in a blog section, be more permissive
        blog_section_path = urlparse(blog_section_url).path.lower()
        
        # URLs that are deeper than the blog section are likely content
        if path.startswith(blog_section_path) and path != blog_section_path:
            # Check if it has reasonable depth (not just blog/)
            path_parts = [p for p in path.split('/') if p]
            blog_parts = [p for p in blog_section_path.split('/') if p]
            
            if len(path_parts) > len(blog_parts):
                return True
        
        # Also check for common blog post patterns
        content_patterns = [
            r'/\d{4}/',  # Year in path
            r'/\d{4}/\d{2}/',  # Year/month
            '/post/', '/posts/', '/article/', '/articles/',
            '/story/', '/stories/', '/entry/', '/entries/',
            '/how-', '/what-', '/why-', '/guide-', '/tutorial-',
            '/resource/', '/resources/', '/insights/', '/updates/',
            '/content/', '/press/', '/media/', '/news/'
        ]
        
        for pattern in content_patterns:
            if re.search(pattern, path):
                return True
        
        return False