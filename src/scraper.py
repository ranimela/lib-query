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

    def run(self) -> IngestionResult:
        """Execute login and scrape coupons.

        Returns:
            IngestionResult containing status and parsed Coupon objects.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--headless=new",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()

                # Step 1: Navigate to Login Page
                logger.info("Navigating to login page...")
                page.goto(self.config.library_login_url, wait_until="domcontentloaded", timeout=30000)

                # Step 2: Fill Auth Credentials
                id_selectors = ["input[name='id']", "input[name='userid']", "input[name='reader_id']", "input[type='text']"]
                pass_selectors = ["input[name='pass']", "input[name='password']", "input[type='password']"]

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
                    browser.close()
                    return IngestionResult(
                        status=IngestionStatus.DOM_MUTATED,
                        error_message="Could not locate login ID or password input fields on page.",
                    )

                page.fill(id_input, self.config.library_id_number)
                page.fill(pass_input, self.config.library_password)

                # Step 3: Submit Login Form
                submit_selectors = ["input[type='submit']", "button[type='submit']", "#submit", "a.button", "button"]
                submit_btn = None
                for sel in submit_selectors:
                    if page.is_visible(sel):
                        submit_btn = sel
                        break

                if submit_btn:
                    page.click(submit_btn)
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(2000)

                # Step 4: Discover all menu links on reader portal
                logger.info("Scanning reader portal navigation links for digital coupons...")
                
                # Base URL for relative link resolution
                base_domain = "https://infocenters.co.il/herzliya/"
                
                # Priority targets + dynamic menu link discovery
                coupon_urls = [self.config.library_coupon_url]
                
                # Query all anchor links in reader navigation menus
                anchors = page.query_selector_all("a[href]")
                for anchor in anchors:
                    href = anchor.get_attribute("href") or ""
                    text = anchor.inner_text().strip()
                    
                    # Target coupon / digital book keywords in Hebrew
                    if any(kw in href.lower() or kw in text for kw in ["dbook", "evrit", "coupon", "שובר", "קופון", "הטבה", "ספרים דיגיטליים"]):
                        full_url = href if href.startswith("http") else f"{base_domain}{href.lstrip('/')}"
                        if full_url not in coupon_urls:
                            coupon_urls.append(full_url)
                            logger.info(f"Discovered potential coupon menu link: '{text}' -> {full_url}")

                # Step 5: Parse Coupons from all discovered pages
                extracted_coupons: list[Coupon] = []
                seen_extracted_ids = set()

                for target_url in coupon_urls:
                    logger.info(f"Scraping page: {target_url}")
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(1500)
                    except Exception as nav_err:
                        logger.warning(f"Could not navigate to {target_url}: {nav_err}")
                        continue

                    # Search for Evrit / coupon code patterns in table rows, cards, or text containers
                    items = page.query_selector_all("tr, div.coupon, div.item, td, div.code_box, p, span")
                    for item in items:
                        text = item.inner_text().strip()
                        if not text or len(text) < 3:
                            continue
                        
                        # Look for keywords related to Evrit / coupons in Hebrew
                        if any(kw in text for kw in ["קוד", "שובר", "עברית", "קופון", "קוד טעינה"]):
                            lines = [line.strip() for line in text.splitlines() if line.strip()]
                            title = lines[0] if lines else "Herzliya Library Digital Coupon"
                            code = ""
                            description = " ".join(lines[1:]) if len(lines) > 1 else text

                            for line in lines:
                                if "קוד" in line or (line.isalnum() and len(line) >= 4):
                                    code = line
                                    break

                            coupon = Coupon(
                                title=title,
                                code=code if code else "See Portal",
                                description=description[:250],
                                link=target_url,
                            )
                            
                            if coupon.item_id not in seen_extracted_ids:
                                seen_extracted_ids.add(coupon.item_id)
                                extracted_coupons.append(coupon)

                browser.close()

                return IngestionResult(
                    status=IngestionStatus.SUCCESS,
                    coupons=extracted_coupons,
                )


        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout occurred during Playwright automation: {e}")
            return IngestionResult(
                status=IngestionStatus.TIMEOUT,
                error_message=f"Page load/action timed out: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unhandled exception in scraper: {e}")
            return IngestionResult(
                status=IngestionStatus.ERROR,
                error_message=str(e),
            )
