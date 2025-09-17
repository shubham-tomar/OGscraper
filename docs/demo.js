// Demo version of OGscraper UI for GitHub Pages
class OGScraperDemo {
    constructor() {
        this.form = document.getElementById('scrape-form');
        this.urlInput = document.getElementById('url');
        this.maxItemsSelect = document.getElementById('max_items');
        this.useBrowserCheckbox = document.getElementById('use_browser');
        this.scrapeBtn = document.getElementById('scrape-btn');
        this.placeholder = document.getElementById('placeholder');
        this.output = document.getElementById('output');
        this.outputCode = this.output.querySelector('code');
        this.errorMessage = document.getElementById('error-message');
        this.copyBtn = document.getElementById('copy-btn');
        this.downloadBtn = document.getElementById('download-btn');
        
        this.currentData = null;
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
        this.copyBtn.addEventListener('click', this.copyToClipboard.bind(this));
        this.downloadBtn.addEventListener('click', this.downloadJSON.bind(this));
        
        this.urlInput.addEventListener('focus', () => {
            this.hideError();
        });
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        const url = this.urlInput.value.trim();
        
        if (!url) {
            this.showError('Please enter a valid URL');
            return;
        }
        
        this.setLoading(true);
        this.hideError();
        this.hideOutput();
        
        // Simulate API call with demo data
        setTimeout(() => {
            const demoData = this.generateDemoData(url);
            this.currentData = demoData;
            this.displayOutput(demoData);
            this.setLoading(false);
        }, 2000);
    }

    generateDemoData(url) {
        const hostname = this.extractHostname(url);
        
        return {
            "site": url,
            "items": [
                {
                    "title": `# ${hostname} - Main Content`,
                    "content": `# Welcome to ${hostname}\n\nThis is a **demo preview** of OGscraper's extraction capabilities.\n\n## What OGscraper Does\n\n- Discovers blog posts and articles automatically\n- Extracts clean, structured content\n- Converts HTML to markdown format\n- Handles complex site structures\n- Filters out navigation and template content\n\n## Real Features\n\nWhen you run OGscraper locally, it will:\n\n### 🔍 Smart Discovery\n- Parse XML sitemaps\n- Follow RSS feeds\n- Navigate through blog directories\n- Use browser automation for JS sites\n\n### 📄 Intelligent Extraction\n- Multiple extraction strategies\n- Template content detection\n- Quality filtering\n- Parallel processing\n\n### 📊 Professional Output\n- Clean markdown formatting\n- Structured JSON results\n- Configurable chunking\n- Export capabilities\n\n---\n\n**To see real extraction from ${hostname}:**\n\n1. Clone the repository\n2. Run \\`python app.py\\`\n3. Visit http://localhost:8080\n4. Enter this URL and get real results!`,
                    "content_type": "blog",
                    "source_url": url
                },
                {
                    "title": `# ${hostname} - Blog Post Example`,
                    "content": `# Sample Blog Post from ${hostname}\n\nThis demonstrates how OGscraper extracts individual blog posts.\n\n## Key Features Demonstrated\n\n### Content Quality\nOGscraper extracts meaningful content while filtering out:\n- Navigation menus\n- Footer content\n- Advertisements\n- Social media widgets\n\n### Markdown Conversion\nHTML elements are cleanly converted:\n- **Headers** maintain hierarchy\n- **Lists** preserve structure  \n- **Links** are properly formatted\n- **Code blocks** are preserved\n\n### Template Detection\nOGscraper automatically detects when multiple URLs serve identical template content and filters duplicates.\n\n---\n\n*This is demo content. Run OGscraper locally to extract real content from any website.*`,
                    "content_type": "blog",
                    "source_url": `${url}/sample-post`
                }
            ],
            "total_items": 2
        };
    }

    extractHostname(url) {
        try {
            return new URL(url.startsWith('http') ? url : 'https://' + url).hostname;
        } catch {
            return 'example.com';
        }
    }

    setLoading(loading) {
        if (loading) {
            this.scrapeBtn.classList.add('loading');
            this.scrapeBtn.disabled = true;
        } else {
            this.scrapeBtn.classList.remove('loading');
            this.scrapeBtn.disabled = false;
        }
    }

    displayOutput(data) {
        const formattedJSON = JSON.stringify(data, null, 2);
        this.outputCode.textContent = formattedJSON;
        
        if (window.Prism) {
            Prism.highlightElement(this.outputCode);
        }
        
        this.placeholder.classList.add('hidden');
        this.output.classList.remove('hidden');
        this.output.classList.add('show');
        
        this.updateOutputHeader(data);
    }

    updateOutputHeader(data) {
        const header = document.querySelector('.output-header h3');
        const itemCount = data.items ? data.items.length : 0;
        header.textContent = `Demo Content (${itemCount} items)`;
    }

    hideOutput() {
        this.placeholder.classList.remove('hidden');
        this.output.classList.add('hidden');
        this.output.classList.remove('show');
        
        const header = document.querySelector('.output-header h3');
        header.textContent = 'Extracted Content';
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorMessage.classList.remove('hidden');
        
        setTimeout(() => {
            this.hideError();
        }, 5000);
    }

    hideError() {
        this.errorMessage.classList.add('hidden');
    }

    async copyToClipboard() {
        if (!this.currentData) return;
        
        try {
            const jsonString = JSON.stringify(this.currentData, null, 2);
            await navigator.clipboard.writeText(jsonString);
            
            const originalText = this.copyBtn.textContent;
            this.copyBtn.textContent = '✅ Copied!';
            this.copyBtn.style.background = 'var(--success-color)';
            this.copyBtn.style.color = 'white';
            
            setTimeout(() => {
                this.copyBtn.textContent = originalText;
                this.copyBtn.style.background = '';
                this.copyBtn.style.color = '';
            }, 2000);
            
        } catch (error) {
            this.showError('Failed to copy to clipboard');
        }
    }

    downloadJSON() {
        if (!this.currentData) return;
        
        const jsonString = JSON.stringify(this.currentData, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const hostname = this.extractHostname(this.currentData.site || 'demo');
        const filename = `ogscraper-demo-${hostname}-${new Date().toISOString().split('T')[0]}.json`;
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        const originalText = this.downloadBtn.textContent;
        this.downloadBtn.textContent = '✅ Downloaded!';
        setTimeout(() => {
            this.downloadBtn.textContent = originalText;
        }, 2000);
    }
}

// Initialize demo when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new OGScraperDemo();
    
    // Add demo notice interaction
    const demoNotice = document.querySelector('.demo-notice');
    if (demoNotice) {
        demoNotice.addEventListener('click', () => {
            demoNotice.style.transform = 'scale(1.02)';
            setTimeout(() => {
                demoNotice.style.transform = 'scale(1)';
            }, 150);
        });
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        document.getElementById('scrape-form').dispatchEvent(new Event('submit'));
    }
    
    if (e.key === 'Escape') {
        document.getElementById('url').value = '';
        document.getElementById('url').focus();
    }
});
