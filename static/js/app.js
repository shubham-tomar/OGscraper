// Modern JavaScript for OGscraper UI
class OGScraperUI {
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
        
        // Auto-expand URL input on focus
        this.urlInput.addEventListener('focus', () => {
            this.hideError();
        });
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        const url = this.urlInput.value.trim();
        const maxItems = parseInt(this.maxItemsSelect.value);
        const useBrowser = this.useBrowserCheckbox.checked;
        
        if (!url) {
            this.showError('Please enter a valid URL');
            return;
        }
        
        this.setLoading(true);
        this.hideError();
        this.hideOutput();
        
        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    max_items: maxItems,
                    use_browser: useBrowser
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to scrape content');
            }
            
            this.currentData = data;
            this.displayOutput(data);
            
        } catch (error) {
            console.error('Scraping error:', error);
            this.showError(error.message || 'An error occurred while scraping');
        } finally {
            this.setLoading(false);
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
        // Format JSON with proper indentation
        const formattedJSON = JSON.stringify(data, null, 2);
        
        // Update the code element
        this.outputCode.textContent = formattedJSON;
        
        // Apply syntax highlighting
        if (window.Prism) {
            Prism.highlightElement(this.outputCode);
        }
        
        // Show output with animation
        this.placeholder.classList.add('hidden');
        this.output.classList.remove('hidden');
        this.output.classList.add('show');
        
        // Add summary info to header
        this.updateOutputHeader(data);
    }

    updateOutputHeader(data) {
        const header = document.querySelector('.output-header h3');
        const itemCount = data.items ? data.items.length : 0;
        header.textContent = `Extracted Content (${itemCount} items)`;
    }

    hideOutput() {
        this.placeholder.classList.remove('hidden');
        this.output.classList.add('hidden');
        this.output.classList.remove('show');
        
        // Reset header
        const header = document.querySelector('.output-header h3');
        header.textContent = 'Extracted Content';
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorMessage.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
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
            
            // Visual feedback
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
        
        // Extract hostname for filename
        const hostname = new URL(this.currentData.site || this.urlInput.value).hostname;
        const filename = `ogscraper-${hostname}-${new Date().toISOString().split('T')[0]}.json`;
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        // Visual feedback
        const originalText = this.downloadBtn.textContent;
        this.downloadBtn.textContent = '✅ Downloaded!';
        setTimeout(() => {
            this.downloadBtn.textContent = originalText;
        }, 2000);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new OGScraperUI();
});

// Add some nice keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to submit form
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        document.getElementById('scrape-form').dispatchEvent(new Event('submit'));
    }
    
    // Escape to clear input
    if (e.key === 'Escape') {
        document.getElementById('url').value = '';
        document.getElementById('url').focus();
    }
});
