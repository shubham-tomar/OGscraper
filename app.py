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

@app.route('/api/scrape', methods=['POST'])
def scrape_endpoint():
    """API endpoint for scraping URLs"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        max_items = data.get('max_items', 10)
        use_browser = data.get('use_browser', False)
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Validate URL format
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
        
        # Create scraper and extract content
        scraper = WebScraper(url, use_browser=use_browser)
        result = scraper.scrape(max_items=max_items)
        
        # Convert to dict for JSON response
        response_data = {
            'site': result.site,
            'items': [
                {
                    'title': item.title,
                    'content': item.content,
                    'content_type': item.content_type,
                    'source_url': item.source_url
                }
                for item in result.items
            ],
            'total_items': len(result.items)
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
