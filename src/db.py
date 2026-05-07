import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY, RETENTION_DAYS

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def run_migrations(self):
        """Create all tables if they don't exist."""
        migrations = [
            self._create_businesses_table,
            self._create_competitors_table,
            self._create_crawl_results_table,
            self._create_crawl_diffs_table,
            self._create_reports_table,
        ]
        for migration in migrations:
            try:
                migration()
                logger.info(f"Migration {migration.__name__} completed")
            except Exception as e:
                logger.error(f"Migration {migration.__name__} failed: {e}")

    def _create_businesses_table(self):
        """Create businesses table."""
        self.client.postgrest.from_("businesses").select("*").limit(1).execute()

    def _create_competitors_table(self):
        """Create competitors table."""
        self.client.postgrest.from_("competitors").select("*").limit(1).execute()

    def _create_crawl_results_table(self):
        """Create crawl_results table."""
        self.client.postgrest.from_("crawl_results").select("*").limit(1).execute()

    def _create_crawl_diffs_table(self):
        """Create crawl_diffs table."""
        self.client.postgrest.from_("crawl_diffs").select("*").limit(1).execute()

    def _create_reports_table(self):
        """Create reports table."""
        self.client.postgrest.from_("reports").select("*").limit(1).execute()

    # Business operations
    def create_business(self, name: str, url: Optional[str], description: Optional[str], user_email: str) -> Dict[str, Any]:
        """Create a new business."""
        business_id = str(uuid.uuid4())
        data = {
            "id": business_id,
            "name": name,
            "url": url,
            "description": description,
            "user_email": user_email,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        result = self.client.postgrest.from_("businesses").insert(data).execute()
        return result.data[0] if result.data else data

    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Get a business by ID."""
        result = self.client.postgrest.from_("businesses").select("*").eq("id", business_id).execute()
        return result.data[0] if result.data else None

    def list_businesses(self) -> List[Dict[str, Any]]:
        """List all businesses."""
        result = self.client.postgrest.from_("businesses").select("*").execute()
        return result.data or []

    # Competitor operations
    def create_competitor(self, business_id: str, name: str, url: str) -> Dict[str, Any]:
        """Create a new competitor."""
        competitor_id = str(uuid.uuid4())
        data = {
            "id": competitor_id,
            "business_id": business_id,
            "name": name,
            "url": url,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.postgrest.from_("competitors").insert(data).execute()
        return result.data[0] if result.data else data

    def get_competitors(self, business_id: str) -> List[Dict[str, Any]]:
        """Get all competitors for a business."""
        result = self.client.postgrest.from_("competitors").select("*").eq("business_id", business_id).eq("is_active", True).execute()
        return result.data or []

    def update_competitor_active(self, competitor_id: str, is_active: bool) -> Dict[str, Any]:
        """Update competitor active status."""
        result = self.client.postgrest.from_("competitors").update({"is_active": is_active}).eq("id", competitor_id).execute()
        return result.data[0] if result.data else {}

    # Crawl results operations
    def create_crawl_result(self, competitor_id: str, sources: Dict[str, Any], status: str = "success", error_message: Optional[str] = None) -> Dict[str, Any]:
        """Create a new crawl result."""
        crawl_id = str(uuid.uuid4())
        data = {
            "id": crawl_id,
            "competitor_id": competitor_id,
            "crawl_timestamp": datetime.utcnow().isoformat(),
            "sources": sources,
            "status": status,
            "error_message": error_message,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.postgrest.from_("crawl_results").insert(data).execute()
        return result.data[0] if result.data else data

    def get_latest_crawl_result(self, competitor_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent crawl result for a competitor."""
        result = self.client.postgrest.from_("crawl_results").select("*").eq("competitor_id", competitor_id).order("crawl_timestamp", desc=True).limit(1).execute()
        return result.data[0] if result.data else None

    def get_previous_crawl_result(self, competitor_id: str, current_crawl_id: str) -> Optional[Dict[str, Any]]:
        """Get the crawl result before the current one."""
        result = self.client.postgrest.from_("crawl_results").select("*").eq("competitor_id", competitor_id).neq("id", current_crawl_id).order("crawl_timestamp", desc=True).limit(1).execute()
        return result.data[0] if result.data else None

    # Crawl diffs operations
    def create_crawl_diff(self, competitor_id: str, previous_crawl_id: str, current_crawl_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new crawl diff."""
        diff_id = str(uuid.uuid4())
        data = {
            "id": diff_id,
            "competitor_id": competitor_id,
            "previous_crawl_id": previous_crawl_id,
            "current_crawl_id": current_crawl_id,
            "changes": changes,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.postgrest.from_("crawl_diffs").insert(data).execute()
        return result.data[0] if result.data else data

    def get_latest_crawl_diffs(self, business_id: str) -> List[Dict[str, Any]]:
        """Get latest diffs for all competitors in a business."""
        # Get all competitors
        competitors = self.get_competitors(business_id)
        competitor_ids = [c["id"] for c in competitors]

        if not competitor_ids:
            return []

        # Get latest diff per competitor
        diffs = []
        for comp_id in competitor_ids:
            result = self.client.postgrest.from_("crawl_diffs").select("*").eq("competitor_id", comp_id).order("created_at", desc=True).limit(1).execute()
            if result.data:
                diffs.append(result.data[0])
        return diffs

    # Report operations
    def create_report(self, business_id: str, report_date: str, full_report_html: str, summary_html: str) -> Dict[str, Any]:
        """Create a new report."""
        report_id = str(uuid.uuid4())
        data = {
            "id": report_id,
            "business_id": business_id,
            "report_date": report_date,
            "full_report_html": full_report_html,
            "summary_html": summary_html,
            "sent_at": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.postgrest.from_("reports").insert(data).execute()
        return result.data[0] if result.data else data

    def get_latest_reports(self, business_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get latest reports for a business."""
        result = self.client.postgrest.from_("reports").select("*").eq("business_id", business_id).order("report_date", desc=True).limit(limit).execute()
        return result.data or []

    # Cleanup operations
    def cleanup_old_crawl_results(self):
        """Delete crawl results older than RETENTION_DAYS."""
        cutoff_date = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        result = self.client.postgrest.from_("crawl_results").delete().lt("created_at", cutoff_date).execute()
        logger.info(f"Deleted crawl results older than {RETENTION_DAYS} days")
        return result

# Global database instance
db = Database()
