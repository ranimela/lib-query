"""Headless web scraping engine for Herzliya Library portal."""

import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.config import Config
from src.models import Coupon, IngestionResult, IngestionStatus

logger = logging.getLogger("lib-query.scraper")


class LibraryScraper:
    """Automates login and coupon extraction for Infocenters library system."""

    def __init__(self, config: Config, headless: bool = True) -> None:
        self.config = config
        self.headless = headless

    def _execute_attempt(self, p) -> IngestionResult:
        """Execute a single browser scraping session."""
        browser = p.chromium.launch(
            headless=self.headless,
            args=[
                "--headless=new",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Step 1: Navigate to Main Site & Login Page
            logger.info("Navigating to main portal root...")
            page.goto("https://infocenters.co.il/herzliya/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)

            logger.info("Navigating to login dialog...")
            page.goto(self.config.library_login_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("#user_id_0", timeout=20000)





            # Step 2: Fill Auth Credentials with keyboard events for IDEA DataWindow
            id_selectors = ["#user_id_0", "input[name='id']", "input[name='userid']", "input[type='text']"]
            pass_selectors = ["#password_0", "input[name='pass']", "input[name='password']", "input[type='password']"]

            id_input = None
            for sel in id_selectors:
                if page.is_visible(sel):
                    id_input = sel
                    break

            pass_input = None
            for sel in pass_selectors:
                if page.is_visible(sel):
                    pass_input = sel
                    break

            if not id_input or not pass_input:
                return IngestionResult(
                    status=IngestionStatus.DOM_MUTATED,
                    error_message="Could not locate login ID or password input fields on page.",
                )

            # Focus, type with keypress events, and blur to update HTDW state
            page.click(id_input)
            page.keyboard.type(self.config.library_id_number, delay=50)
            page.evaluate(f"document.querySelector('{id_input}').blur()")

            page.click(pass_input)
            page.keyboard.type(self.config.library_password, delay=50)
            page.evaluate(f"document.querySelector('{pass_input}').blur()")

            # Step 3: Submit Login Form via HTDW handler
            logger.info("Submitting login form...")
            try:
                page.evaluate("htmldw.buttonPress('Update', 0, 'b_login', 0)")
            except Exception as e:
                logger.warning(f"JS buttonPress failed ({e}), clicking login button directly...")
                page.click("#b_login_0")

            page.wait_for_timeout(4000)

            # Solidify session by visiting main portal home page
            logger.info("Solidifying authenticated session on portal root...")
            page.goto("https://infocenters.co.il/herzliya/site.asp?site=herzliya", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)





            # Step 4: Discover all menu links on reader portal
            logger.info("Scanning reader portal navigation links for digital coupons...")
            
            base_domain = "https://infocenters.co.il/herzliya/"
            coupon_urls = [self.config.library_coupon_url]
            
            anchors = page.query_selector_all("a[href]")
            for anchor in anchors:
                href = anchor.get_attribute("href") or ""
                text = anchor.inner_text().strip()
                
                if any(kw in href.lower() or kw in text for kw in ["dbook", "evrit", "coupon", "שובר", "קופון", "הטבה", "ספרים דיגיטליים"]):
                    full_url = href if href.startswith("http") else f"{base_domain}{href.lstrip('/')}"
                    if full_url not in coupon_urls:
                        coupon_urls.append(full_url)
                        logger.info(f"Discovered potential coupon menu link: '{text}' -> {full_url}")

            # Step 5: Parse Coupons from all discovered pages
            import re
            extracted_coupons: list[Coupon] = []
            seen_extracted_ids = set()

            for target_url in coupon_urls:
                logger.info(f"Scraping page: {target_url}")
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4000)
                except Exception as nav_err:
                    logger.warning(f"Could not navigate to {target_url}: {nav_err}")
                    continue

                # Parse coupon codes directly from page text and table content
                frames_to_check = page.frames if page.frames else [page.main_frame]
                for frame in frames_to_check:
                    try:
                        frame_html = frame.content()
                        frame_text = frame.inner_text("body")

                        # Match active e-vrit coupon codes (e.g. herABBRZQFEH)
                        matches = set(re.findall(r"\b(her[A-Za-z0-9]{6,20})\b", frame_html + "\n" + frame_text))
                        for code_val in matches:
                            coupon = Coupon(
                                title=f"e-vrit Digital Coupon ({code_val})",
                                code=code_val,
                                description=f"Active Digital Coupon Code: {code_val} | Vendor: e-vrit",
                                link=target_url,
                            )
                            if coupon.item_id not in seen_extracted_ids:
                                seen_extracted_ids.add(coupon.item_id)
                                extracted_coupons.append(coupon)

                    except Exception as frame_err:
                        logger.warning(f"Could not scan frame {frame.url}: {frame_err}")








            return IngestionResult(
                status=IngestionStatus.SUCCESS,
                coupons=extracted_coupons,
            )
        finally:
            browser.close()

    def run(self, max_retries: int = 2) -> IngestionResult:
        """Execute login and scrape coupons with retry attempts for network resilience.

        Args:
            max_retries: Number of retry attempts on transient network/timeout errors.

        Returns:
            IngestionResult containing status and parsed Coupon objects.
        """
        last_error = ""
        with sync_playwright() as p:
            for attempt in range(1, max_retries + 1):
                logger.info(f"Starting scraper attempt {attempt}/{max_retries}...")
                try:
                    res = self._execute_attempt(p)
                    if res.status == IngestionStatus.SUCCESS:
                        return res
                    last_error = res.error_message or f"Attempt status: {res.status.value}"
                    logger.warning(f"Attempt {attempt} returned non-success: {last_error}")
                except PlaywrightTimeoutError as e:
                    last_error = f"Page load/action timed out (attempt {attempt}/{max_retries}): {str(e)}"
                    logger.warning(last_error)
                except Exception as e:
                    last_error = f"Scraper error (attempt {attempt}/{max_retries}): {str(e)}"
                    logger.warning(last_error)

        logger.error(f"All {max_retries} scraper attempts failed. Last error: {last_error}")
        return IngestionResult(
            status=IngestionStatus.ERROR,
            error_message=last_error or "All scraper attempts failed.",
        )
