"""
Modern web interface for OGscraper
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import asyncio
import json
from ogscraper.scraper import WebScraper
from ogscraper.models import ScrapingResult

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    """Serve the main UI"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'service': 'ogscraper',
        'version': '1.0.0'
    })

@app.route('/api/scrape', methods=['POST'])
def scrape_endpoint():
    """API endpoint for scraping URLs with production optimizations"""
    import time
    import logging

    start_time = time.time()
    logger = logging.getLogger(__name__)

    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        max_items = min(data.get('max_items', 10), 20)  # Cap at 20 for production
        use_browser = data.get('use_browser', False)

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Validate URL format
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url

        logger.info(f"Starting scrape request for {url} (max_items={max_items})")

        # Create scraper with production-optimized settings
        scraper = WebScraper(
            url,
            use_browser=use_browser,
            max_concurrent=10,  # Reduced for production stability
            chunk_size=6000    # Smaller chunks for faster processing
        )

        result = scraper.scrape(max_items=max_items)

        processing_time = time.time() - start_time
        logger.info(f"Scraping completed in {processing_time:.2f}s, found {len(result.items)} items")

        # Convert to dict for JSON response
        response_data = {
            'site': result.site,
            'items': [
                {
                    'title': item.title,
                    'content': item.content[:5000],  # Truncate content for production
                    'content_type': item.content_type,
                    'source_url': item.source_url
                }
                for item in result.items
            ],
            'total_items': len(result.items),
            'processing_time': round(processing_time, 2)
        }

        return jsonify(response_data)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Scraping failed after {processing_time:.2f}s: {str(e)}")
        return jsonify({
            'error': str(e),
            'processing_time': round(processing_time, 2)
        }), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
