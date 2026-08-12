"""Main CLI Entrypoint for Library Digital Coupon Notifier."""

import logging
import sys
from pathlib import Path

# Ensure absolute project directory context for Windows Task Scheduler
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.models import IngestionStatus
from src.notifier import Notifier
from src.scraper import LibraryScraper
from src.state_manager import StateManager

# Ensure UTF-8 stream handling for Windows console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("lib-query.main")



def run_pipeline() -> int:
    """Execute the end-to-end scraper, deduplication, and notification pipeline.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    logger.info("Initializing lib-query pipeline...")

    # Load Configuration
    try:
        config = Config.load()
    except Exception as e:
        logger.critical(f"Configuration load failure: {e}")
        # Attempt emergency ntfy alert if default URL is present
        notifier = Notifier(ntfy_topic_url="https://ntfy.sh/lib-query-ranimela")
        notifier.notify_failure("Configuration Error", str(e))
        return 1

    notifier = Notifier(ntfy_topic_url=config.ntfy_topic_url)
    state_manager = StateManager(state_file_path=config.state_file_path)
    scraper = LibraryScraper(config=config, headless=True)

    # Step 1: Execute Scraper Ingestion
    logger.info("Starting browser automation scraper...")
    result = scraper.run()

    if result.status != IngestionStatus.SUCCESS:
        error_msg = result.error_message or f"Scraper finished with status {result.status.value}"
        logger.error(f"Scraper execution failed: {error_msg}")
        notifier.notify_failure(f"Scraper ({result.status.value})", error_msg)
        return 1

    logger.info(f"Scraper completed successfully. Found {len(result.coupons)} raw coupon item(s).")

    # Step 2: Deduplication
    new_coupons = state_manager.filter_new_coupons(result.coupons)
    logger.info(f"Deduplication complete. {len(new_coupons)} novel coupon(s) ready for notification.")

    if not new_coupons:
        logger.info("No new coupons discovered today. Pipeline finished.")
        notifier.notify_status("Checked Herzliya Library portal — 0 new coupons discovered today.")
        return 0


    # Step 3: Dispatch Alerts & Record State
    successfully_notified = []
    for coupon in new_coupons:
        logger.info(f"Dispatching ntfy alert for coupon: {coupon.title} (ID: {coupon.item_id})")
        success = notifier.notify_coupon(coupon)
        if success:
            successfully_notified.append(coupon)
            logger.info(f"Successfully notified coupon {coupon.item_id}")
        else:
            logger.warning(f"Failed to dispatch ntfy alert for coupon {coupon.item_id}")

    if successfully_notified:
        state_manager.record_processed(successfully_notified)
        logger.info(f"Updated state.json with {len(successfully_notified)} new entry/entries.")

    return 0


if __name__ == "__main__":
    sys.exit(run_pipeline())
