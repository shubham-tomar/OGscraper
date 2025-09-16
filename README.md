# OGscraper

A powerful, intelligent web scraper designed to extract blog content and technical knowledge from any website. Built to handle diverse site structures with zero manual configuration.

## 🚀 Features

- **Universal Site Support**: Works with any blog or content site without custom configuration
- **Multiple Discovery Methods**: Combines sitemap parsing, RSS feeds, navigation discovery, and blog path detection
- **Intelligent Content Extraction**: Uses multiple extraction strategies with automatic fallbacks
- **Template Content Detection**: Automatically filters out duplicate template content served on blog URLs
- **Parallel Processing**: Fast concurrent extraction with configurable connection limits
- **Browser Support**: Optional browser-based extraction for JavaScript-heavy sites
- **Smart Deduplication**: Content-based and URL-based deduplication with template detection
- **Markdown Output**: Clean, structured markdown content ready for knowledge bases

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/shubham-tomar/OGscraper.git
cd OGscraper

# Install dependencies
pip install -r requirements.txt

# Or using uv (recommended)
uv pip install -r requirements.txt
```

## 🔧 Usage

### Web Interface (Recommended)

The easiest way to use OGscraper is through the modern web interface:

```bash
# Start the web server
python app.py
# or
uv run python app.py

# Open your browser to http://localhost:8080
```

**Features:**
- ✨ Modern, intuitive interface
- 📱 Responsive design for mobile/desktop
- 🎨 Syntax-highlighted JSON output
- 📋 One-click copy/download results
- ⚙️ Easy configuration options

### Command Line Interface

```bash
# Basic usage
python -m ogscraper.cli https://example.com

# Extract specific number of items
python -m ogscraper.cli https://quill.co --max-items 5

# Use browser-based extraction for JavaScript sites
python -m ogscraper.cli https://example.com --browser

# Enable verbose logging
python -m ogscraper.cli https://example.com --verbose

# Custom chunk size for large content
python -m ogscraper.cli https://example.com --chunk-size 10000
```

### Python API

```python
from ogscraper.scraper import WebScraper

# Basic scraping
scraper = WebScraper("https://example.com")
result = scraper.scrape(max_items=10)

# With browser support
scraper = WebScraper("https://example.com", use_browser=True)
result = scraper.scrape(max_items=10)

# Access results
for item in result.items:
    print(f"Title: {item.title}")
    print(f"Content: {item.content[:200]}...")
    print(f"URL: {item.source_url}")
```

### REST API

The web interface also exposes a REST API endpoint:

```bash
# POST /api/scrape
curl -X POST http://localhost:8080/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_items": 10, "use_browser": false}'
```

## 🎯 Output Format

```json
{
  "site": "https://example.com",
  "items": [
    {
      "title": "Blog Post Title",
      "content": "# Blog Post Title\n\nMarkdown formatted content...",
      "content_type": "blog",
      "source_url": "https://example.com/blog/post-title"
    }
  ]
}
```

## 🧠 How It Works

OGscraper uses a multi-strategy approach to discover and extract content:

### 1. URL Discovery
- **Sitemap Parsing**: Extracts URLs from XML sitemaps
- **RSS Feed Detection**: Discovers content from RSS/Atom feeds  
- **Blog Path Discovery**: Searches common blog directories (`/blog`, `/articles`, `/resource`, etc.)
- **Navigation Discovery**: Follows navigation links to find blog sections
- **Browser Discovery**: Uses browser automation for JavaScript-rendered content

### 2. Content Extraction
- **Multi-Extractor Pipeline**: Combines Trafilatura, Readability, and custom extractors
- **Smart Content Detection**: Identifies main content while filtering navigation/footer
- **Template Content Filtering**: Detects and filters duplicate template content
- **Markdown Conversion**: Converts HTML to clean, structured markdown

### 3. Content Processing
- **Intelligent Deduplication**: Content-based hashing with template detection
- **Smart Chunking**: Splits large content at natural paragraph boundaries
- **Quality Filtering**: Removes low-quality or navigation-heavy content

## 🌐 Tested Sites

OGscraper has been tested and works well with:

- **Tech Blogs**: quill.co, interviewing.io
- **Business Sites**: thebluedot.co, franchiseki.com
- **Personal Blogs**: Various Substack and custom blog platforms
- **Documentation Sites**: Sites with `/docs` or `/guides` sections
- **News Sites**: Sites with `/news` or `/press` sections

## 🛠 CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max-items` | Maximum number of items to extract | 100 |
| `--chunk-size` | Maximum size for content chunks (characters) | 8000 |
| `--browser` | Use browser-based extraction | False |
| `--verbose` | Enable verbose logging | False |
| `--parallel/--no-parallel` | Enable/disable parallel processing | True |
| `--max-concurrent` | Maximum concurrent connections | 10 |

## 🔍 Advanced Features

### Template Content Detection

OGscraper automatically detects when blog URLs serve identical template content instead of unique posts:

```bash
# Example: thebluedot.co serves template content on blog URLs
python -m ogscraper.cli https://www.thebluedot.co/ --max-items 5
# Output: "Detected 5 items with identical content - likely generic page extraction failure"
# Result: Filters out template content, keeps one representative item
```

### Navigation-Based Discovery

For sites where content is only accessible through navigation:

```bash
# Example: quill.co requires clicking navigation to access docs
python -m ogscraper.cli https://quill.co/ --browser
# Automatically follows navigation links to discover content
```

### Direct URL Extraction

Extract content from specific URLs:

```bash
# Extract from a specific blog post
python -m ogscraper.cli "https://example.com/blog/specific-post"
# Bypasses discovery, extracts directly from the given URL
```
