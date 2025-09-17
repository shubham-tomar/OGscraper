"""
Browser-based rendering for JavaScript-heavy websites
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext


logger = logging.getLogger(__name__)


class PlaywrightRenderer:
    """Handles browser-based rendering for JavaScript-heavy sites"""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def __aenter__(self):
        """Async context manager entry"""
        import os
        import shutil
        self.playwright = await async_playwright().start()

        # Try to find system Chromium (Railway/Nix environment)
        chromium_paths = [
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/bin/chromium',
            shutil.which('chromium'),
            shutil.which('chromium-browser')
        ]

        system_chromium = None
        for path in chromium_paths:
            if path and os.path.exists(path):
                system_chromium = path
                logger.info(f"Found system Chromium at: {path}")
                break

        if system_chromium and (os.environ.get('PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD') == '1' or os.path.exists('/nix/store')):
            # Use system Chromium in Nix/Railway environment
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                executable_path=system_chromium
            )
        else:
            # Fallback to downloaded browsers
            self.browser = await self.playwright.chromium.launch(headless=self.headless)

        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def render_page(self, url: str, wait_for_selector: Optional[str] = None) -> Dict[str, Any]:
        """Render a page and return HTML content with metadata"""
        if not self.context:
            raise RuntimeError("Renderer not initialized. Use as async context manager.")

        page = await self.context.new_page()

        try:
            # Navigate to page
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')

            # Wait for specific selector if provided
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=5000)
                except Exception:
                    logger.debug(f"Selector {wait_for_selector} not found on {url}")

            # Wait a bit more for dynamic content
            await page.wait_for_timeout(2000)

            # Get page content and metadata
            html_content = await page.content()
            title = await page.title()

            # Get all links
            links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(link => ({
                        href: link.href,
                        text: link.textContent?.trim() || '',
                        title: link.title || ''
                    }));
                }
            """)

            return {
                'html': html_content,
                'title': title,
                'url': url,
                'links': links,
                'final_url': page.url
            }

        except Exception as exc:
            logger.error(f"Failed to render {url}: {exc}")
            return {
                'html': '',
                'title': '',
                'url': url,
                'links': [],
                'final_url': url,
                'error': str(exc)
            }
        finally:
            await page.close()

    async def discover_dynamic_urls(self, base_url: str, selectors: List[str] = None) -> List[str]:
        """Discover URLs from JavaScript-rendered content"""
        if selectors is None:
            selectors = [
                'a[href*="blog"]',
                'a[href*="article"]',
                'a[href*="post"]',
                '.blog-post a',
                '.article-link',
                '[data-testid*="blog"] a',
                '.post-title a'
            ]

        result = await self.render_page(base_url)
        if result.get('error'):
            return []

        urls = set()
        domain = urlparse(base_url).netloc

        # Extract URLs from links found during rendering
        for link in result.get('links', []):
            href = link.get('href', '')
            if href:
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)

                # Same domain and looks like content
                if parsed.netloc == domain and self._is_content_url(full_url):
                    urls.add(full_url)

        # Try to discover blog posts by interaction
        interaction_urls = await self._discover_by_interaction(base_url)
        urls.update(interaction_urls)

        # Try to capture XHR/API calls that might load more content
        await self._capture_api_calls(base_url, urls)

        return list(urls)

    async def _discover_by_interaction(self, base_url: str) -> List[str]:
        """Discover URLs by interacting with page elements (clicking, etc.)"""
        if not self.context:
            return []

        page = await self.context.new_page()
        urls = set()
        domain = urlparse(base_url).netloc

        try:
            await page.goto(base_url, timeout=self.timeout, wait_until='networkidle')
            await page.wait_for_timeout(2000)

            # Look for clickable blog post elements
            clickable_elements = await page.evaluate('''
                () => {
                    const elements = [];

                    // Find potential blog post containers
                    const selectors = [
                        'h1, h2, h3',  // Headers that might be clickable
                        '[class*="post"]',
                        '[class*="blog"]',
                        '[class*="article"]',
                        '[class*="card"]',
                        'article'
                    ];

                    selectors.forEach(selector => {
                        const els = document.querySelectorAll(selector);
                        els.forEach(el => {
                            const text = el.textContent?.trim() || '';
                            const rect = el.getBoundingClientRect();

                            // Only consider visible elements with reasonable text
                            if (text.length > 10 && text.length < 200 &&
                                rect.width > 0 && rect.height > 0) {

                                // Check if element or parent is clickable
                                const isClickable = el.onclick ||
                                                  el.closest('a') ||
                                                  el.closest('[onclick]') ||
                                                  el.closest('[role="button"]') ||
                                                  getComputedStyle(el).cursor === 'pointer';

                                if (isClickable) {
                                    elements.push({
                                        text: text.substring(0, 100),
                                        selector: selector,
                                        index: elements.length
                                    });
                                }
                            }
                        });
                    });

                    return elements.slice(0, 10); // Limit to first 10
                }
            ''')

            logger.debug(f"Found {len(clickable_elements)} clickable elements on {base_url}")

            # Try clicking each element and capture navigation
            for element in clickable_elements:
                try:
                    # Create a new page for each click to avoid state issues
                    click_page = await self.context.new_page()
                    await click_page.goto(base_url, wait_until='networkidle')

                    # Wait for page load
                    await click_page.wait_for_timeout(1000)

                    # Find and click the element
                    element_handle = await click_page.query_selector(f'{element["selector"]}')
                    if element_handle:
                        # Get all matching elements and find the right one by text
                        all_elements = await click_page.query_selector_all(element["selector"])
                        for el in all_elements:
                            el_text = await el.text_content()
                            if el_text and element["text"] in el_text:
                                try:
                                    # Try to click
                                    await el.click(timeout=3000)
                                    await click_page.wait_for_timeout(2000)

                                    # Check if we navigated to a new URL
                                    current_url = click_page.url
                                    if current_url != base_url and domain in current_url:
                                        if self._is_content_url(current_url):
                                            urls.add(current_url)
                                            logger.debug(f"Found URL via click: {current_url}")

                                    break
                                except Exception:
                                    continue

                    await click_page.close()

                except Exception as e:
                    logger.debug(f"Failed to interact with element: {e}")
                    continue

            # Also try looking for data attributes that might contain URLs
            data_urls = await page.evaluate('''
                () => {
                    const urls = [];
                    const elements = document.querySelectorAll('[data-href], [data-url], [data-link], [data-slug]');

                    elements.forEach(el => {
                        const url = el.dataset.href || el.dataset.url || el.dataset.link || el.dataset.slug;
                        if (url) {
                            urls.push(url);
                        }
                    });

                    return urls;
                }
            ''')

            for url in data_urls:
                full_url = urljoin(base_url, url)
                parsed = urlparse(full_url)
                if parsed.netloc == domain and self._is_content_url(full_url):
                    urls.add(full_url)

        except Exception as e:
            logger.warning(f"Interaction discovery failed for {base_url}: {e}")
        finally:
            await page.close()

        return list(urls)

    async def _capture_api_calls(self, base_url: str, urls: set) -> None:
        """Capture API calls that might return more URLs"""
        if not self.context:
            return

        page = await self.context.new_page()
        api_responses = []

        # Listen for response events
        async def handle_response(response):
            if response.url.endswith(('.json', '/api/', '/graphql')) or 'api' in response.url:
                try:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'json' in content_type:
                            json_data = await response.json()
                            api_responses.append({
                                'url': response.url,
                                'data': json_data
                            })
                except Exception:
                    pass

        page.on('response', handle_response)

        try:
            await page.goto(base_url, timeout=self.timeout, wait_until='networkidle')
            await page.wait_for_timeout(3000)  # Wait for API calls

            # Extract URLs from API responses
            domain = urlparse(base_url).netloc
            for response in api_responses:
                self._extract_urls_from_json(response['data'], base_url, domain, urls)

        except Exception as exc:
            logger.debug(f"Failed to capture API calls for {base_url}: {exc}")
        finally:
            await page.close()

    def _extract_urls_from_json(self, data: Any, base_url: str, domain: str, urls: set) -> None:
        """Extract URLs from JSON API responses"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['url', 'link', 'href', 'slug', 'path']:
                    if isinstance(value, str):
                        full_url = urljoin(base_url, value)
                        if urlparse(full_url).netloc == domain and self._is_content_url(full_url):
                            urls.add(full_url)
                else:
                    self._extract_urls_from_json(value, base_url, domain, urls)
        elif isinstance(data, list):
            for item in data:
                self._extract_urls_from_json(item, base_url, domain, urls)

    def _is_content_url(self, url: str) -> bool:
        """Check if URL likely contains content"""
        path = urlparse(url).path.lower()
        full_url = url.lower()

        # Skip common non-content paths
        skip_patterns = [
            '/tag/', '/category/', '/author/', '/page/',
            '/search', '/login', '/register', '/contact',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js',
            '/api/', '/admin/', '/comments', '/share',
            '/subscribe', '/unsubscribe', '/archive',
            '/about', '/privacy', '/terms'
        ]

        for pattern in skip_patterns:
            if pattern in path:
                return False

        # Platform-specific filtering
        if 'substack.com' in full_url:
            # Skip comment pages and tag pages
            if '/comments' in path or '/t/' in path:
                return False
            # Prefer actual post URLs (format: /p/post-title)
            if '/p/' in path and not path.endswith('/comments'):
                return True

        # Prefer paths that look like content
        content_indicators = [
            '/blog/', '/post/', '/article/', '/news/',
            '/guide/', '/tutorial/', '/story/', '/p/'  # Substack uses /p/
        ]

        for indicator in content_indicators:
            if indicator in path:
                return True

        # Also accept if path has reasonable length and structure
        return len(path) > 1 and path != '/' and path.count('/') >= 2


def sync_render_page(url: str, **kwargs) -> Dict[str, Any]:
    """Synchronous wrapper for page rendering"""
    async def _render():
        async with PlaywrightRenderer(**kwargs) as renderer:
            return await renderer.render_page(url)

    return asyncio.run(_render())


def sync_discover_urls(base_url: str, **kwargs) -> List[str]:
    """Synchronous wrapper for URL discovery"""
    async def _discover():
        async with PlaywrightRenderer(**kwargs) as renderer:
            return await renderer.discover_dynamic_urls(base_url)

    return asyncio.run(_discover())