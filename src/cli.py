import sys
import logging
from typing import Optional
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from src.db import db
from src.competitors import identify_competitors, format_competitors_for_review
from src.scheduler import scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

@click.group()
def cli():
    """Competitive Research Tracker CLI"""
    pass

@cli.command()
@click.option("--name", prompt="Business name", help="Name of your business")
@click.option("--url", default=None, help="Business URL (optional)")
@click.option("--description", default=None, help="Business description (optional)")
@click.option("--email", prompt="Your email", help="Email for daily reports")
def add_business(name: str, url: Optional[str], description: Optional[str], email: str):
    """Add a new business to track competitors for."""
    try:
        console.print(f"\n📊 Setting up competitive tracking for [bold]{name}[/bold]...")

        # Create business
        business = db.create_business(name, url, description, email)
        console.print(f"✓ Business created: {business['id']}")

        # Identify competitors
        console.print("\n🔍 Identifying competitors...")
        console.print("(This may take a moment...)")

        competitors_list = identify_competitors(name, url, description)

        if not competitors_list:
            console.print("[red]✗ Failed to identify competitors. Try again later.[/red]")
            return

        # Display for review
        console.print(format_competitors_for_review(competitors_list))

        # Confirm
        if not click.confirm("Save these competitors?"):
            console.print("[yellow]Cancelled - no competitors saved[/yellow]")
            return

        # Save competitors
        saved_count = 0
        for comp in competitors_list:
            try:
                db.create_competitor(business['id'], comp['name'], comp['url'])
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save competitor {comp['name']}: {e}")

        console.print(f"\n✓ Saved {saved_count} competitors")

        # Offer to run first crawl
        console.print(f"\nBusiness ID: [bold]{business['id']}[/bold]")
        if click.confirm("Run first crawl now?"):
            console.print("Starting crawl...")
            success = scheduler.run_daily_crawl_for_business(business['id'])
            if success:
                console.print("[green]✓ First crawl completed![/green]")
                console.print(f"Report sent to {email}")
            else:
                console.print("[yellow]⚠ Crawl had errors - check logs[/yellow]")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        logger.error(e, exc_info=True)

@cli.command()
def list_businesses():
    """List all businesses being tracked."""
    try:
        businesses = db.list_businesses()

        if not businesses:
            console.print("[yellow]No businesses configured yet.[/yellow]")
            return

        table = Table(title="Configured Businesses")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Email", style="blue")
        table.add_column("Competitors", style="magenta")
        table.add_column("Created", style="dim")

        for business in businesses:
            competitors = db.get_competitors(business['id'])
            created = business['created_at'][:10] if 'created_at' in business else "N/A"
            table.add_row(
                business['id'][:8],
                business['name'],
                business['user_email'],
                str(len(competitors)),
                created
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")

@cli.command()
@click.argument("business_id")
def crawl_now(business_id: str):
    """Manually trigger a crawl for a business."""
    try:
        business = db.get_business(business_id)
        if not business:
            console.print(f"[red]✗ Business not found: {business_id}[/red]")
            return

        console.print(f"🚀 Starting crawl for [bold]{business['name']}[/bold]...")

        success = scheduler.run_daily_crawl_for_business(business_id)

        if success:
            console.print("[green]✓ Crawl completed successfully![/green]")
            console.print(f"Report sent to {business['user_email']}")
        else:
            console.print("[red]✗ Crawl failed - check logs[/red]")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        logger.error(e, exc_info=True)

@cli.command()
@click.argument("business_id")
@click.option("--limit", default=5, help="Number of recent reports to show")
def view_reports(business_id: str, limit: int):
    """View past reports for a business."""
    try:
        business = db.get_business(business_id)
        if not business:
            console.print(f"[red]✗ Business not found: {business_id}[/red]")
            return

        reports = db.get_latest_reports(business_id, limit)

        if not reports:
            console.print(f"[yellow]No reports found for {business['name']}[/yellow]")
            return

        console.print(f"\n📄 Recent Reports for {business['name']}:")
        console.print("-" * 50)

        for idx, report in enumerate(reports, 1):
            sent_at = report.get('sent_at', report.get('created_at', 'N/A'))
            sent_date = sent_at[:10] if isinstance(sent_at, str) else str(sent_at)[:10]
            console.print(f"{idx}. Report from {sent_date}")

        console.print("-" * 50)
        console.print(f"\nTo view full report details, open the HTML file or check your email.")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")

@cli.command()
@click.argument("business_id")
def show_competitors(business_id: str):
    """Show competitors for a business."""
    try:
        business = db.get_business(business_id)
        if not business:
            console.print(f"[red]✗ Business not found: {business_id}[/red]")
            return

        competitors = db.get_competitors(business_id)

        if not competitors:
            console.print(f"[yellow]No competitors configured for {business['name']}[/yellow]")
            return

        table = Table(title=f"Competitors for {business['name']}")
        table.add_column("Name", style="green")
        table.add_column("URL", style="cyan")
        table.add_column("Status", style="magenta")

        for comp in competitors:
            status = "Active" if comp.get('is_active') else "Paused"
            table.add_row(comp['name'], comp['url'], status)

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")

@cli.command()
@click.argument("business_id")
@click.option("--name", prompt="Competitor name", help="Company name")
@click.option("--url", prompt="Competitor URL", help="Company website URL")
def add_competitor(business_id: str, name: str, url: str):
    """Manually add a competitor to a business."""
    try:
        business = db.get_business(business_id)
        if not business:
            console.print(f"[red]✗ Business not found: {business_id}[/red]")
            return

        db.create_competitor(business_id, name, url)
        console.print(f"✓ Added competitor: {name}")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")

def main():
    """Entry point for CLI."""
    try:
        cli()
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        logger.error(e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
