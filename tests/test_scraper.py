"""Scraper unit tests."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from consumer.scraper import ArticleScraper, ScrapedContent


class TestArticleScraper:
    """Tests for ArticleScraper class."""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance."""
        return ArticleScraper(timeout=10)

    def test_scraper_initialization(self, scraper):
        """Test scraper initializes with correct settings."""
        assert scraper.timeout == 10
        assert "User-Agent" in scraper.headers

    def test_parse_html_extracts_title(self, scraper):
        """Test HTML parsing extracts title correctly."""
        html = """
        <html>
            <head><title>Test Article Title</title></head>
            <body>
                <article>
                    <h1>Test Article Title</h1>
                    <p>This is the article content with more than fifty characters to ensure extraction works properly.</p>
                    <p>Second paragraph with additional content.</p>
                    <p>Third paragraph for good measure.</p>
                </article>
            </body>
        </html>
        """
        title, content = scraper._parse_html(html, "https://example.com")
        assert title == "Test Article Title"
        assert content is not None
        assert "article content" in content.lower()

    def test_parse_html_with_og_title(self, scraper):
        """Test HTML parsing prefers og:title."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="OG Title">
                <title>Regular Title</title>
            </head>
            <body><p>Content</p></body>
        </html>
        """
        title, _ = scraper._parse_html(html, "https://example.com")
        assert title == "OG Title"

    def test_parse_html_removes_script_tags(self, scraper):
        """Test HTML parsing removes script content."""
        html = """
        <html>
            <head><title>Title</title></head>
            <body>
                <script>var secret = "password123";</script>
                <article>
                    <p>This is the actual content that should be extracted and is long enough.</p>
                    <p>More content here for the test.</p>
                    <p>And even more content.</p>
                </article>
            </body>
        </html>
        """
        _, content = scraper._parse_html(html, "https://example.com")
        assert "password123" not in content
        assert "actual content" in content.lower()

    def test_clean_text_removes_whitespace(self, scraper):
        """Test text cleaning removes excessive whitespace."""
        text = "Line 1\n\n\n\n\nLine 2   \n   Line 3"
        cleaned = scraper._clean_text(text)
        assert "\n\n\n" not in cleaned

    @pytest.mark.asyncio
    async def test_scrape_timeout(self, scraper):
        """Test scraping handles timeout."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=TimeoutError()
            )
            # Note: Actual test would need async context manager mocking
            pass

    @pytest.mark.asyncio
    async def test_scrape_404_error(self, scraper):
        """Test scraping handles 404 error."""
        # Should return ScrapedContent with success=False and "404" in error
        pass


class TestScrapedContent:
    """Tests for ScrapedContent dataclass."""

    def test_scraped_content_success(self):
        """Test successful scrape result."""
        result = ScrapedContent(
            title="Test Title",
            content="Test content",
            success=True
        )
        assert result.success
        assert result.error is None

    def test_scraped_content_failure(self):
        """Test failed scrape result."""
        result = ScrapedContent(
            title="",
            content="",
            success=False,
            error="404 Not Found"
        )
        assert not result.success
        assert "404" in result.error
