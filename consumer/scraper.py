"""Web scraper for article content extraction."""
import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup
from shared.config import settings


@dataclass
class ScrapedContent:
    """Container for scraped article content."""
    title: str
    content: str
    success: bool
    error: Optional[str] = None


class ArticleScraper:
    """Scraper for extracting article content from web pages."""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.scrape_timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape article content from the given URL.

        Returns ScrapedContent with title, content, and success status.
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=self.headers
            ) as session:
                async with session.get(url, ssl=False) as response:
                    if response.status == 404:
                        return ScrapedContent(
                            title="",
                            content="",
                            success=False,
                            error="404 Not Found"
                        )

                    if response.status == 403:
                        return ScrapedContent(
                            title="",
                            content="",
                            success=False,
                            error="403 Forbidden - Access denied"
                        )

                    if response.status >= 400:
                        return ScrapedContent(
                            title="",
                            content="",
                            success=False,
                            error=f"HTTP Error {response.status}"
                        )

                    html = await response.text()
                    title, content = self._parse_html(html, url)

                    if not content:
                        return ScrapedContent(
                            title=title or "Unknown Title",
                            content="",
                            success=False,
                            error="Failed to extract article content"
                        )

                    return ScrapedContent(
                        title=title or "Unknown Title",
                        content=content,
                        success=True
                    )

        except asyncio.TimeoutError:
            return ScrapedContent(
                title="",
                content="",
                success=False,
                error=f"Timeout after {self.timeout} seconds"
            )
        except aiohttp.ClientError as e:
            return ScrapedContent(
                title="",
                content="",
                success=False,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            return ScrapedContent(
                title="",
                content="",
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

    def _parse_html(self, html: str, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse HTML and extract title and main content.

        Uses multiple strategies to find article content.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = self._extract_title(soup)

        # Remove unwanted elements
        for element in soup.find_all(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript"]):
            element.decompose()

        # Extract content using multiple strategies
        content = self._extract_content(soup)

        return title, content

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title from HTML."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try regular title tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main article content using multiple strategies."""
        content = None

        # Strategy 1: Look for article tag
        article = soup.find("article")
        if article:
            content = self._clean_text(article.get_text(separator="\n"))
            if len(content) > 100:
                return content

        # Strategy 2: Look for common article containers
        for selector in ["main", ".article-content", ".post-content", ".entry-content",
                        "#article-body", ".article-body", ".story-body", ".content"]:
            element = soup.select_one(selector)
            if element:
                content = self._clean_text(element.get_text(separator="\n"))
                if len(content) > 100:
                    return content

        # Strategy 3: Look for largest div with paragraphs
        divs = soup.find_all("div")
        best_div = None
        max_paragraphs = 0

        for div in divs:
            paragraphs = div.find_all("p")
            if len(paragraphs) > max_paragraphs:
                max_paragraphs = len(paragraphs)
                best_div = div

        if best_div and max_paragraphs >= 3:
            content = self._clean_text(best_div.get_text(separator="\n"))
            if len(content) > 100:
                return content

        # Strategy 4: Get all paragraphs
        paragraphs = soup.find_all("p")
        if paragraphs:
            text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50)
            if text:
                return text

        # Fallback: Get body text
        body = soup.find("body")
        if body:
            return self._clean_text(body.get_text(separator="\n"))[:10000]

        return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]

        # Join and limit length
        cleaned = "\n\n".join(lines)

        # Limit to reasonable length
        if len(cleaned) > 50000:
            cleaned = cleaned[:50000] + "..."

        return cleaned
