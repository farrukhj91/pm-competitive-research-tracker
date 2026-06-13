import logging
import sys
from typing import Optional
from datetime import datetime

from src.db import db
from src.crawler import crawler
from src.diff import diff_engine
from src.report_generator import report_generator
from src.email_sender import email_sender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Scheduler:
    """Orchestrate the entire crawl → diff → report → send workflow."""

    def run_daily_crawl_for_business(self, business_id: str) -> str:
        """Run complete crawl cycle for a single business.

        Returns one of:
          - "success" — crawl completed (possibly with some per-competitor errors)
          - "skipped" — business has no competitors yet; not an error
          - "failed"  — fatal error, the run should be flagged
        """
        try:
            logger.info(f"Starting daily crawl for business {business_id}")

            # Get business
            business = db.get_business(business_id)
            if not business:
                logger.error(f"Business {business_id} not found")
                return "failed"

            logger.info(f"Crawling for business: {business['name']}")

            # Get competitors
            competitors = db.get_competitors(business_id)
            if not competitors:
                # Not a failure — onboarding in progress, business paused, or
                # user hasn't picked competitors yet. Skip cleanly so we
                # don't spam the GitHub Actions failure email.
                logger.info(f"No competitors configured for business {business_id} — skipping")
                return "skipped"

            logger.info(f"Found {len(competitors)} competitors")

            # Crawl all competitors
            all_diffs = []
            crawl_sources_map = {}  # competitor_id -> sources (for initial comprehensive analysis)
            crawl_errors = []

            for competitor in competitors:
                try:
                    logger.info(f"Crawling {competitor['name']} ({competitor['url']})")

                    # Run crawler
                    crawl_sources = crawler.crawl_competitor(
                        competitor['name'],
                        competitor['url'],
                        linkedin_url=competitor.get('linkedin_url'),
                    )
                    crawl_sources_map[competitor['id']] = crawl_sources

                    # Store crawl result
                    crawl_result = db.create_crawl_result(
                        competitor_id=competitor['id'],
                        sources=crawl_sources,
                        status="success"
                    )

                    # Get previous crawl
                    previous_crawl = db.get_previous_crawl_result(competitor['id'], crawl_result['id'])

                    # Generate diff
                    diff_data = diff_engine.generate_diff(
                        previous_crawl['sources'] if previous_crawl else None,
                        crawl_sources
                    )

                    # Store diff
                    if not diff_data.get("is_first_crawl"):
                        db.create_crawl_diff(
                            competitor_id=competitor['id'],
                            previous_crawl_id=previous_crawl['id'] if previous_crawl else None,
                            current_crawl_id=crawl_result['id'],
                            changes=diff_data.get("changes", {})
                        )

                    all_diffs.append({
                        "competitor_id": competitor['id'],
                        "is_first_crawl": diff_data.get("is_first_crawl"),
                        "changes": diff_data.get("changes", {}),
                    })

                    logger.info(f"✓ Completed crawl for {competitor['name']}")

                except Exception as e:
                    logger.error(f"Error crawling {competitor['name']}: {e}")
                    crawl_errors.append(f"{competitor['name']}: {str(e)}")
                    continue

            # Generate report
            logger.info("Generating report...")
            try:
                report = report_generator.generate_report(
                    business=business,
                    competitors=competitors,
                    diffs=all_diffs,
                    crawl_sources_map=crawl_sources_map,
                )

                # Store report
                db.create_report(
                    business_id=business_id,
                    report_date=datetime.now().strftime('%Y-%m-%d'),
                    full_report_html=report['full_report'],
                    summary_html=report['summary']
                )

                # Send email
                logger.info(f"Sending email to {business['user_email']}")
                email_sent = email_sender.send_report(
                    recipient_email=business['user_email'],
                    business_name=business['name'],
                    full_report_html=report['full_report'],
                    summary_html=report['summary']
                )

                if not email_sent:
                    logger.error("Failed to send report email")
                    return "failed"

            except Exception as e:
                logger.error(f"Error generating report: {e}")
                crawl_errors.append(f"Report generation: {str(e)}")

            # Log summary
            if crawl_errors:
                logger.warning(f"Completed with {len(crawl_errors)} errors:")
                for error in crawl_errors:
                    logger.warning(f"  - {error}")
                # Partial success is still success; only mark failed if
                # every competitor errored.
                if len(crawl_errors) < len(competitors):
                    return "success"
                else:
                    return "failed"

            logger.info(f"✓ Daily crawl completed successfully for {business['name']}")
            return "success"

        except Exception as e:
            logger.error(f"Fatal error in daily crawl: {e}")
            # Try to send error notification
            try:
                business = db.get_business(business_id)
                if business:
                    email_sender.send_error_report(
                        recipient_email=business['user_email'],
                        error_message=str(e)
                    )
            except Exception as email_error:
                logger.error(f"Failed to send error notification: {email_error}")
            return "failed"

    def run_all_active_businesses(self) -> bool:
        """Run daily crawl for all active businesses.

        Returns False (exit 1) only if any business actually FAILED.
        Businesses that are skipped (no competitors) do NOT count as failure —
        they're a normal state during onboarding.
        """
        businesses = db.list_businesses()
        logger.info(f"Running crawls for {len(businesses)} businesses")

        results = {}
        for business in businesses:
            status = self.run_daily_crawl_for_business(business['id'])
            results[business['name']] = status

        # Log summary
        successful = sum(1 for v in results.values() if v == "success")
        skipped = sum(1 for v in results.values() if v == "skipped")
        failed = sum(1 for v in results.values() if v == "failed")
        logger.info(
            f"Completed: {successful} successful, {skipped} skipped, "
            f"{failed} failed (out of {len(businesses)} businesses)"
        )

        # Only flag the run as failed if there was a real failure
        return failed == 0

    def cleanup_old_data(self):
        """Delete old crawl results (data retention)."""
        try:
            logger.info("Running data cleanup...")
            db.cleanup_old_crawl_results()
            logger.info("Data cleanup completed")
        except Exception as e:
            logger.error(f"Error during data cleanup: {e}")

scheduler = Scheduler()

def main():
    """CLI entry point for manual scheduler execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Run competitive research crawler")
    parser.add_argument("--business-id", help="Run crawl for specific business ID")
    parser.add_argument("--all", action="store_true", help="Run crawl for all businesses")
    parser.add_argument("--cleanup", action="store_true", help="Run data cleanup")

    args = parser.parse_args()

    if args.cleanup:
        scheduler.cleanup_old_data()
    elif args.business_id:
        status = scheduler.run_daily_crawl_for_business(args.business_id)
        # success and skipped both mean "nothing went wrong"
        sys.exit(1 if status == "failed" else 0)
    elif args.all:
        success = scheduler.run_all_active_businesses()
        sys.exit(0 if success else 1)
    else:
        # Default: run for all businesses
        success = scheduler.run_all_active_businesses()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
