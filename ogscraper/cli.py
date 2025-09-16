"""
Command line interface for OGScraper
"""

import json
import logging
from typing import Optional

import click

from .scraper import WebScraper


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


@click.command()
@click.argument('url')
@click.option(
    '--max-items',
    default=100,
    help='Maximum number of items to scrape',
    type=int
)
@click.option(
    '--output',
    '-o',
    help='Output file path (default: print to stdout)',
    type=click.Path()
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--chunk-size',
    default=8000,
    help='Maximum size for content chunks',
    type=int
)
@click.option(
    '--browser',
    '-b',
    is_flag=True,
    help='Use browser rendering for JavaScript-heavy sites'
)
@click.option(
    '--parallel/--sequential',
    default=True,
    help='Use parallel processing for faster extraction (default: parallel)'
)
@click.option(
    '--max-concurrent',
    default=10,
    help='Maximum concurrent connections for parallel processing',
    type=int
)
def main(
    url: str,
    max_items: int,
    output: Optional[str],
    verbose: bool,
    chunk_size: int,
    browser: bool,
    parallel: bool,
    max_concurrent: int
) -> None:
    """Scrape content from a website and output as JSON

    Examples:
        ogscraper https://interviewing.io/blog
        ogscraper https://blog.example.com --max-items 50 --output results.json
        ogscraper https://site.com/blog -v --chunk-size 5000
    """
    setup_logging(verbose)

    try:
        scraper = WebScraper(
            url,
            chunk_size=chunk_size,
            use_browser=browser,
            parallel=parallel,
            max_concurrent=max_concurrent
        )
        result = scraper.scrape(max_items)

        json_output = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(json_output)
            click.echo(f"Results saved to {output}")
        else:
            click.echo(json_output)

    except KeyboardInterrupt:
        click.echo("\nScraping interrupted by user", err=True)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    main()