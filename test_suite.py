#!/usr/bin/env python3
"""
Comprehensive Website Scraping Test Suite
Tests the OGscraper against various website categories and generates performance reports.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests
from tabulate import tabulate
import sys
import os

# Add the project directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ogscraper.async_extractors import AsyncMultiExtractor

class WebsiteTestSuite:
    """Comprehensive test suite for website scraping"""
    
    def __init__(self):
        self.test_websites = {
            "Personal & Substack Blogs": [
                "https://shreycation.substack.com",
                "https://paulgraham.com/articles.html",
                "https://nilmamano.com/blog/category/dsa",
                "https://seths.blog",
                "https://www.gatesnotes.com"
            ],
            "SaaS & Startup Blogs": [
                "https://quill.co/blog",
                "https://lioness.io",
                "https://www.interviewing.io/blog",
                "https://linear.app/blog",
                "https://notion.so/blog",
                "https://zapier.com/blog",
                "https://airbyte.com/blog",
                "https://vercel.com/blog",
                "https://openai.com/research",
                "https://figma.com/blog"
            ],
            "Company / Product Guides & Docs": [
                "https://resilio.com/blog",
                "https://biconnector.com/blog",
                "https://thebluedot.co/blog",
                "https://assorthealth.com/blog",
                "https://franchiseki.com/blog",
                "https://stripe.com/blog",
                "https://developer.hashicorp.com/blog",
                "https://about.gitlab.com/blog",
                "https://aws.amazon.com/blogs/architecture/",
                "https://cloud.google.com/blog"
            ],
            "News / Magazine Style": [
                "https://techcrunch.com",
                "https://thenextweb.com",
                "https://wired.com",
                "https://nytimes.com/section/technology",
                "https://theguardian.com/international/technology"
            ],
            "Technical Blogs & Guides": [
                "https://martinfowler.com/articles",
                "https://kubernetes.io/blog",
                "https://developers.cloudflare.com/fundamentals/",
                "https://realpython.com",
                "https://pytorch.org/blog",
                "https://towardsdatascience.com"
            ],
            "Podcast / Transcript Sites": [
                "https://lexfridman.com/podcast",
                "https://changelog.com/podcast",
                "https://acquired.fm/episodes"
            ],
            "Other Formats": [
                "https://arxiv.org"
            ]
        }
        
        self.results = []
        self.summary_stats = {}

    async def test_website(self, url: str, use_browser: bool = False, max_items: int = 5) -> Dict:
        """Test a single website and return results"""
        start_time = time.time()
        
        result = {
            'url': url,
            'use_browser': use_browser,
            'max_items': max_items,
            'success': False,
            'items_found': 0,
            'time_taken': 0,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            async with AsyncMultiExtractor(use_browser=use_browser, max_concurrent=1) as extractor:
                items = await extractor.extract_content_parallel([url])
                
                result['success'] = len(items) > 0
                result['items_found'] = len(items) if items else 0
                result['time_taken'] = time.time() - start_time
                
                # Store first few items for sample
                if items and len(items) > 0:
                    result['sample_items'] = [
                        {
                            'title': item.title[:100] if item.title else 'No title',
                            'url': item.source_url,
                            'content_preview': item.content[:150] + '...' if len(item.content) > 150 else item.content,
                            'content_type': item.content_type
                        }
                        for item in items[:1]  # Just first item for brevity
                    ]
            
        except Exception as e:
            result['time_taken'] = time.time() - start_time
            result['error'] = str(e)
            
        return result

    async def run_comprehensive_test(self):
        """Run tests on all websites with both browser and non-browser modes"""
        print("🚀 Starting Comprehensive Website Scraping Test Suite")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        total_tests = 0
        for category_urls in self.test_websites.values():
            total_tests += len(category_urls) * 2  # Both browser and non-browser modes
            
        print(f"📊 Total tests to run: {total_tests}")
        print()
        
        for category, urls in self.test_websites.items():
            print(f"\n🔍 Testing Category: {category}")
            print("-" * 60)
            
            for url in urls:
                print(f"  Testing: {url}")
                
                # Test without browser
                print("    🌐 Non-browser mode... ", end="", flush=True)
                result_no_browser = await self.test_website(url, use_browser=False)
                self.results.append(result_no_browser)
                
                status = "✅ SUCCESS" if result_no_browser['success'] else "❌ FAILED"
                time_str = f"{result_no_browser['time_taken']:.2f}s"
                items_str = f"{result_no_browser['items_found']} items"
                print(f"{status} ({time_str}, {items_str})")
                
                # Test with browser
                print("    🖥️  Browser mode... ", end="", flush=True)
                result_browser = await self.test_website(url, use_browser=True)
                self.results.append(result_browser)
                
                status = "✅ SUCCESS" if result_browser['success'] else "❌ FAILED"
                time_str = f"{result_browser['time_taken']:.2f}s"
                items_str = f"{result_browser['items_found']} items"
                print(f"{status} ({time_str}, {items_str})")
                
                # Small delay to be respectful
                await asyncio.sleep(1)

    def generate_summary_stats(self):
        """Generate summary statistics from test results"""
        stats = {
            'total_tests': len(self.results),
            'successful_tests': len([r for r in self.results if r['success']]),
            'failed_tests': len([r for r in self.results if not r['success']]),
            'browser_mode_tests': len([r for r in self.results if r['use_browser']]),
            'non_browser_mode_tests': len([r for r in self.results if not r['use_browser']]),
            'avg_time_all': sum(r['time_taken'] for r in self.results) / len(self.results),
            'avg_time_success': 0,
            'avg_items_found': sum(r['items_found'] for r in self.results) / len(self.results),
            'total_items_found': sum(r['items_found'] for r in self.results)
        }
        
        successful_results = [r for r in self.results if r['success']]
        if successful_results:
            stats['avg_time_success'] = sum(r['time_taken'] for r in successful_results) / len(successful_results)
        
        # Category-wise stats
        stats['by_category'] = {}
        for category, urls in self.test_websites.items():
            category_results = [r for r in self.results if any(r['url'] == url for url in urls)]
            if category_results:
                stats['by_category'][category] = {
                    'total': len(category_results),
                    'successful': len([r for r in category_results if r['success']]),
                    'avg_time': sum(r['time_taken'] for r in category_results) / len(category_results),
                    'total_items': sum(r['items_found'] for r in category_results)
                }
        
        # Mode comparison
        browser_results = [r for r in self.results if r['use_browser']]
        non_browser_results = [r for r in self.results if not r['use_browser']]
        
        stats['mode_comparison'] = {
            'browser': {
                'success_rate': len([r for r in browser_results if r['success']]) / len(browser_results) * 100,
                'avg_time': sum(r['time_taken'] for r in browser_results) / len(browser_results),
                'avg_items': sum(r['items_found'] for r in browser_results) / len(browser_results)
            },
            'non_browser': {
                'success_rate': len([r for r in non_browser_results if r['success']]) / len(non_browser_results) * 100,
                'avg_time': sum(r['time_taken'] for r in non_browser_results) / len(non_browser_results),
                'avg_items': sum(r['items_found'] for r in non_browser_results) / len(non_browser_results)
            }
        }
        
        self.summary_stats = stats

    def print_detailed_report(self):
        """Print comprehensive test report"""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE TEST REPORT")
        print("=" * 80)
        
        # Overall Summary
        print(f"\n📊 OVERALL SUMMARY")
        print("-" * 40)
        print(f"Total Tests Run: {self.summary_stats['total_tests']}")
        print(f"Successful: {self.summary_stats['successful_tests']} ({self.summary_stats['successful_tests']/self.summary_stats['total_tests']*100:.1f}%)")
        print(f"Failed: {self.summary_stats['failed_tests']} ({self.summary_stats['failed_tests']/self.summary_stats['total_tests']*100:.1f}%)")
        print(f"Average Time: {self.summary_stats['avg_time_all']:.2f}s")
        print(f"Total Items Found: {self.summary_stats['total_items_found']}")
        print(f"Average Items per Test: {self.summary_stats['avg_items_found']:.1f}")
        
        # Mode Comparison
        print(f"\n🔄 MODE COMPARISON")
        print("-" * 40)
        browser_stats = self.summary_stats['mode_comparison']['browser']
        non_browser_stats = self.summary_stats['mode_comparison']['non_browser']
        
        comparison_data = [
            ["Metric", "Browser Mode", "Non-Browser Mode"],
            ["Success Rate", f"{browser_stats['success_rate']:.1f}%", f"{non_browser_stats['success_rate']:.1f}%"],
            ["Average Time", f"{browser_stats['avg_time']:.2f}s", f"{non_browser_stats['avg_time']:.2f}s"],
            ["Average Items", f"{browser_stats['avg_items']:.1f}", f"{non_browser_stats['avg_items']:.1f}"]
        ]
        print(tabulate(comparison_data, headers="firstrow", tablefmt="grid"))
        
        # Category Performance
        print(f"\n📚 CATEGORY PERFORMANCE")
        print("-" * 40)
        category_data = [["Category", "Success Rate", "Avg Time", "Total Items"]]
        for category, stats in self.summary_stats['by_category'].items():
            success_rate = stats['successful'] / stats['total'] * 100
            category_data.append([
                category[:30] + "..." if len(category) > 30 else category,
                f"{success_rate:.1f}%",
                f"{stats['avg_time']:.2f}s",
                stats['total_items']
            ])
        print(tabulate(category_data, headers="firstrow", tablefmt="grid"))
        
        # Top Performers and Problem Sites
        successful_results = [r for r in self.results if r['success']]
        failed_results = [r for r in self.results if not r['success']]
        
        if successful_results:
            print(f"\n⚡ FASTEST SUCCESSFUL SCRAPES")
            print("-" * 40)
            fastest = sorted(successful_results, key=lambda x: x['time_taken'])[:10]
            fastest_data = [["URL", "Mode", "Time", "Items"]]
            for result in fastest:
                mode = "Browser" if result['use_browser'] else "Non-Browser"
                fastest_data.append([
                    result['url'][:50] + "..." if len(result['url']) > 50 else result['url'],
                    mode,
                    f"{result['time_taken']:.2f}s",
                    result['items_found']
                ])
            print(tabulate(fastest_data, headers="firstrow", tablefmt="grid"))
        
        if failed_results:
            print(f"\n❌ FAILED TESTS")
            print("-" * 40)
            failed_data = [["URL", "Mode", "Error"]]
            for result in failed_results:
                mode = "Browser" if result['use_browser'] else "Non-Browser"
                error = result['error'][:60] + "..." if result['error'] and len(result['error']) > 60 else result['error']
                failed_data.append([
                    result['url'][:40] + "..." if len(result['url']) > 40 else result['url'],
                    mode,
                    error or "Unknown error"
                ])
            print(tabulate(failed_data, headers="firstrow", tablefmt="grid"))

    def save_results(self, filename: str = None):
        """Save detailed results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results_{timestamp}.json"
        
        output = {
            'metadata': {
                'test_run_date': datetime.now().isoformat(),
                'total_websites': sum(len(urls) for urls in self.test_websites.values()),
                'total_tests': len(self.results)
            },
            'summary_statistics': self.summary_stats,
            'detailed_results': self.results,
            'test_websites': self.test_websites
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {filename}")
        return filename

async def main():
    """Main test execution function"""
    print("🔧 Initializing Website Test Suite...")
    
    suite = WebsiteTestSuite()
    
    try:
        await suite.run_comprehensive_test()
        suite.generate_summary_stats()
        suite.print_detailed_report()
        filename = suite.save_results()
        
        print(f"\n✅ Test suite completed successfully!")
        print(f"📁 Detailed results saved to: {filename}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Test suite interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
