import os
import time
import uuid
import base64
import logging
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from app.config import settings

logger = logging.getLogger("threads_agent.playwright")


class PlaywrightToolManager:
    def __init__(self, headless: bool = True, imgbb_api_key: Optional[str] = None):
        self.headless = headless
        self.imgbb_api_key = imgbb_api_key
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session_file = Path(settings.SESSIONS_PATH) / "threads_session.json"
        self.is_finished = False
        self.finish_status = "unknown"
        self.finish_url = None
        self.finish_summary = None

    async def start(self):
        self.playwright = await async_playwright().start()
        
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certifcate-errors",
            "--ignore-certifcate-errors-spki-list",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=launch_args
        )

        if self.session_file.exists():
            try:
                self.context = await self.browser.new_context(
                    storage_state=str(self.session_file),
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
                logger.info("Loaded existing session from storage_state.json")
            except Exception as e:
                logger.warning(f"Failed to load session file: {e}")
                self.context = await self.browser.new_context(
                    viewport={"width": 1280, "height": 800}
                )
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800}
            )

        self.page = await self.context.new_page()
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)

    async def save_session(self):
        if self.context:
            try:
                await self.context.storage_state(path=str(self.session_file))
                logger.info("Saved browser session state.")
                return True
            except Exception as e:
                logger.error(f"Failed to save session state: {e}")
                return False
        return False

    async def close(self):
        if self.context:
            await self.save_session()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str) -> str:
        if not self.page:
            return "Error: Browser not started"
        try:
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=settings.BROWSER_TIMEOUT_MS)
            await self.page.wait_for_timeout(2500)
            status = response.status if response else "unknown"
            return f"Navigated to {url}. Current URL: {self.page.url}. HTTP Status: {status}"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"

    async def ensure_threads_login(self, username: str, password: str) -> Dict[str, Any]:
        """
        1. Cek apakah session ID yang tersimpan masih valid di Threads.
           Jika masih valid, langsung gunakan tanpa perlu login lagi.
        2. Jika session ID belum ada atau sudah expired, lakukan login otomatis dengan
           username dan password, lalu simpan session ID yang baru ke file session.
        """
        if not self.page:
            return {"success": False, "error": "Browser page belum terinisialisasi"}
        try:
            logger.info("Memeriksa status session ID login Threads...")
            await self.navigate("https://www.threads.com")
            await self.page.wait_for_timeout(3500)

            # Cek apakah halaman adalah halaman login atau sudah feed
            has_password_field = await self.page.locator('input[type="password"], input[autocomplete="current-password"]').count() > 0
            is_login_page = "login" in self.page.url or has_password_field

            # Kasus 1: Sesi tersimpan masih valid (Session ID aktif)
            if not is_login_page and self.session_file.exists():
                ss = await self.take_screenshot(prefix="login_active_session")
                logger.info(f"Valid & active session at {self.page.url}. Continuing without re-login.")
                return {
                    "success": True,
                    "message": f"Active & valid Session ID loaded ({self.page.url}). Reusing session without re-login.",
                    "screenshot": ss
                }

            # Case 2: Session expired or no session ID yet
            if self.session_file.exists():
                logger.warning("Saved session ID is expired or logged out. Starting automated re-login...")
            else:
                logger.info("No saved session ID found. Opening https://www.threads.com/login...")

            if "login" not in self.page.url:
                await self.navigate("https://www.threads.com/login")
                await self.page.wait_for_timeout(3000)

            # Check credentials availability
            if not username or not password:
                ss = await self.take_screenshot(prefix="login_missing_credentials")
                return {
                    "success": False,
                    "error": "Session ID expired / not found, and Threads Username or Password is not set in Admin Settings.",
                    "screenshot": ss
                }

            logger.info(f"Filling Threads login form for '{username}'...")
            
            # Input username
            user_input = self.page.locator('input[autocomplete="username"], input[name="username"], input[placeholder*="Username"], input[placeholder*="email"], input[type="text"]').first
            if await user_input.count() > 0:
                await user_input.click()
                await user_input.fill(username)
            else:
                ss = await self.take_screenshot(prefix="login_no_user_input")
                return {
                    "success": False,
                    "error": "Username/email input field not found on https://www.threads.com/login.",
                    "screenshot": ss
                }

            # Input password
            pass_input = self.page.locator('input[autocomplete="current-password"], input[type="password"], input[name="password"]').first
            if await pass_input.count() > 0:
                await pass_input.click()
                await pass_input.fill(password)
            else:
                ss = await self.take_screenshot(prefix="login_no_pass_input")
                return {
                    "success": False,
                    "error": "Password input field not found on https://www.threads.com/login.",
                    "screenshot": ss
                }

            # Submit login
            submit_btn = self.page.locator('input[type="submit"], button[type="submit"], div[role="button"]:has-text("Log in"), div[role="button"]:has-text("Masuk")')
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
            else:
                await pass_input.press("Enter")

            # Wait for response
            await self.page.wait_for_timeout(6000)

            # Check for error / incorrect credentials
            error_el = self.page.locator('div[role="alert"], p[role="alert"], div:has-text("Incorrect password"), div:has-text("Kata sandi salah"), div:has-text("Sorry, your password was incorrect"), div:has-text("Couldn\'t find your account")')
            if await error_el.count() > 0:
                err_text = (await error_el.first.inner_text()).strip()
                ss = await self.take_screenshot(prefix="login_incorrect_password")
                return {
                    "success": False,
                    "error": f"Threads login rejected: {err_text or 'Incorrect Username or Password.'}",
                    "screenshot": ss
                }

            # Check for 2FA / checkpoint
            if "checkpoint" in self.page.url or "challenge" in self.page.url:
                ss = await self.take_screenshot(prefix="login_checkpoint")
                return {
                    "success": False,
                    "error": f"Threads account requires extra security verification (2FA/Challenge): {self.page.url}",
                    "screenshot": ss
                }

            # Stuck on login page
            if await self.page.locator('input[type="password"]').count() > 0 and "login" in self.page.url:
                ss = await self.take_screenshot(prefix="login_stuck")
                return {
                    "success": False,
                    "error": f"Login did not advance past the login page ({self.page.url}). Verify username and password.",
                    "screenshot": ss
                }

            # Save new session ID
            await self.save_session()
            ss = await self.take_screenshot(prefix="login_success")
            logger.info(f"Threads login successful. New session ID saved to {self.session_file}.")
            return {
                "success": True,
                "message": f"Login successful and Session ID saved for subsequent runs ({self.page.url}).",
                "screenshot": ss
            }
        except Exception as e:
            logger.error(f"Error during login process: {e}", exc_info=True)
            ss = await self.take_screenshot(prefix="login_error")
            return {
                "success": False,
                "error": f"Exception on login step: {str(e)}",
                "screenshot": ss
            }

    async def find_viral_threads(
        self,
        min_comments: int = 100,
        min_likes: int = 100,
        commented_urls: set = None,
        max_scrolls: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Menjelajahi feed Threads dan mendeteksi postingan viral dengan:
        komentar >= min_comments ATAU likes >= min_likes.
        Mengabaikan thread yang sudah ada di commented_urls.
        """
        if not self.page:
            return []
        
        commented_urls = commented_urls or set()
        viral_threads = []

        try:
            await self.navigate("https://www.threads.com")
            await self.page.wait_for_timeout(3500)

            js_scanner = """
            () => {
                function parseCount(str) {
                    if (!str) return 0;
                    str = str.toLowerCase().replace(/,/g, '.').trim();
                    let multiplier = 1;
                    if (str.includes('k') || str.includes('rb')) multiplier = 1000;
                    else if (str.includes('m') || str.includes('jt')) multiplier = 1000000;
                    const match = str.match(/([0-9]+(?:\\.[0-9]+)?)/);
                    return match ? Math.round(parseFloat(match[1]) * multiplier) : 0;
                }

                const results = [];
                const origin = window.location.origin || 'https://www.threads.com';
                const containers = document.querySelectorAll('div[data-pressable-container="true"], article, div[role="article"]');
                
                containers.forEach(container => {
                    const linkEl = container.querySelector('a[href*="/post/"], a[href*="/t/"]');
                    if (!linkEl) return;
                    let href = linkEl.getAttribute('href') || '';
                    if (href.startsWith('/')) href = origin + href;
                    href = href.split('?')[0];

                    const authorEl = container.querySelector('a[href^="/@"]');
                    const author = authorEl ? authorEl.innerText.trim() : '';

                    // Extract post content text
                    let contentText = '';
                    const textElements = container.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                    textElements.forEach(el => {
                        const t = (el.innerText || '').trim();
                        if (t.length > contentText.length && !t.includes('http')) {
                            contentText = t;
                        }
                    });

                    let likeCount = 0;
                    let commentCount = 0;

                    // 1. Precise Detection via SVGs and closest Buttons/Parent spans
                    const svgs = container.querySelectorAll('svg');
                    svgs.forEach(svg => {
                        const aria = (svg.getAttribute('aria-label') || '').toLowerCase();
                        const title = (svg.querySelector('title') ? svg.querySelector('title').textContent : '').toLowerCase();
                        const pathD = svg.querySelector('path') ? (svg.querySelector('path').getAttribute('d') || '') : '';
                        const btn = svg.closest('button, div[role="button"]') || svg.parentElement;
                        const btnText = btn ? (btn.innerText || '').trim() : '';
                        const parentText = btn && btn.parentElement ? (btn.parentElement.innerText || '').trim() : '';

                        const isLike = aria.includes('like') || aria.includes('suka') || title.includes('like') || title.includes('suka') || pathD.startsWith('M16.5 2');
                        const isReply = aria.includes('reply') || aria.includes('balas') || aria.includes('comment') || title.includes('reply') || title.includes('balas') || pathD.startsWith('M12 3C7');

                        if (isLike) {
                            const count = parseCount(btnText) || parseCount(parentText);
                            if (count > likeCount) likeCount = count;
                        } else if (isReply) {
                            const count = parseCount(btnText) || parseCount(parentText);
                            if (count > commentCount) commentCount = count;
                        }
                    });

                    // 2. Action Bar Numeric Buttons Fallback in standard order [Like, Reply, Repost, Share]
                    if (likeCount === 0 && commentCount === 0) {
                        const numButtons = Array.from(container.querySelectorAll('div[role="button"], button'))
                            .map(b => (b.innerText || '').trim())
                            .filter(t => /^[0-9.,]+[kKmM]?$/.test(t));
                        
                        if (numButtons.length >= 2) {
                            likeCount = parseCount(numButtons[0]);
                            commentCount = parseCount(numButtons[1]);
                        }
                    }

                    // 3. Fallback: text regex matching
                    if (likeCount === 0 || commentCount === 0) {
                        const fullText = container.innerText || '';
                        const commentMatches = fullText.matchAll(/([0-9.,]+(?:k|rb|m)?)\\s*(?:balasan|replies|komentar|comments)/gi);
                        for (const m of commentMatches) {
                            const count = parseCount(m[1]);
                            if (count > commentCount) commentCount = count;
                        }

                        const likeMatches = fullText.matchAll(/([0-9.,]+(?:k|rb|m)?)\\s*(?:suka|likes|like)/gi);
                        for (const m of likeMatches) {
                            const count = parseCount(m[1]);
                            if (count > likeCount) likeCount = count;
                        }
                    }

                    if (href) {
                        results.push({
                            url: href,
                            author: author,
                            text: contentText.slice(0, 350) || author || 'Threads Post',
                            comment_count: commentCount,
                            like_count: likeCount
                        });
                    }
                });

                return results;
            }
            """

            for scroll_step in range(max_scrolls):
                batch = await self.page.evaluate(js_scanner)
                for item in batch:
                    u = item["url"]
                    if u not in commented_urls and not any(v["url"] == u for v in viral_threads):
                        # Requirement: Comments >= min_comments OR Likes >= min_likes
                        if item["comment_count"] >= min_comments or item["like_count"] >= min_likes:
                            viral_threads.append(item)

                # Scroll down to load more items
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await self.page.wait_for_timeout(2000)

            logger.info(f"Found {len(viral_threads)} viral threads matching criteria (>= {min_comments} comments OR >= {min_likes} likes).")
            return viral_threads

        except Exception as e:
            logger.error(f"Error scanning viral threads: {e}")
            return []

    async def reply_to_thread(self, thread_url: str, comment_text: str) -> Dict[str, Any]:
        """
        Navigasi ke thread viral dan memposting komentar balasan promosi produk.
        """
        if not self.page:
            return {"success": False, "error": "Browser not initialized"}

        try:
            await self.navigate(thread_url)
            await self.page.wait_for_timeout(3000)

            # 1. Locate reply textbox: div[role="textbox"][contenteditable="true"]
            reply_input = self.page.locator('div[role="textbox"][contenteditable="true"]')
            reply_btn = self.page.get_by_role("button", name="Reply").or_(self.page.get_by_text("Reply to")).or_(self.page.get_by_text("Balas"))

            if await reply_input.count() > 0:
                await reply_input.first.click()
            elif await reply_btn.count() > 0:
                await reply_btn.first.click()
            else:
                return {
                    "success": False,
                    "error": "Reply textbox or reply button not found on page",
                    "screenshot": await self.take_screenshot(prefix="reply_box_not_found")
                }

            await self.page.wait_for_timeout(1000)

            # 2. Type comment text using keyboard to trigger Lexical synthetic input events
            active_box = self.page.locator('div[role="textbox"][contenteditable="true"]').first
            await active_box.click()
            await self.page.wait_for_timeout(500)
            await self.page.keyboard.type(comment_text, delay=15)
            await self.page.wait_for_timeout(1500)

            before_screenshot = await self.take_screenshot(prefix="before_reply")

            # 3. Locate and click the exact submit button in the composer
            clicked_res = await self.page.evaluate("""() => {
                const box = document.querySelector('div[role="textbox"][contenteditable="true"]');
                if (!box) return { clicked: false, reason: 'Textbox not found' };

                // 1. Search upwards in the composer hierarchy for the rotated submit arrow button
                let p = box;
                for (let i = 0; i < 8; i++) {
                    if (!p) break;
                    const submitBtn = p.querySelector('div[role="button"]:has(svg[aria-label="Reply"]), div[role="button"]:has(svg[aria-label="Balas"])');
                    if (submitBtn && submitBtn.innerHTML.includes('rotate(90deg)')) {
                        submitBtn.click();
                        return { clicked: true, method: 'composer_arrow_svg' };
                    }
                    p = p.parentElement;
                }

                // 2. Search for any button with text Post or Balas or Kirim
                const allButtons = Array.from(document.querySelectorAll('button, div[role="button"]'));
                for (const b of allButtons) {
                    const text = (b.innerText || '').trim();
                    const aria = b.getAttribute('aria-label') || '';
                    if (text === 'Post' || text === 'Balas' || text === 'Kirim' || aria === 'Post' || aria === 'Balas') {
                        b.click();
                        return { clicked: true, method: 'text_button_' + text };
                    }
                }

                return { clicked: false, reason: 'No submit button matched' };
            }""")

            if not clicked_res.get("clicked"):
                fallback_btn = self.page.locator('div[role="button"]:has(svg[aria-label="Reply"]), div[role="button"]:has(svg[aria-label="Balas"]), button:has-text("Post"), button:has-text("Balas")').first
                if await fallback_btn.count() > 0:
                    await fallback_btn.click()
                else:
                    return {
                        "success": False,
                        "error": f"Failed to submit comment: {clicked_res.get('reason', 'Submit button not found')}",
                        "screenshot": before_screenshot
                    }

            # 4. Verification: wait and verify that the comment was actually submitted
            is_submitted = False
            for _ in range(8):
                await self.page.wait_for_timeout(1000)
                box_state = await self.page.evaluate("""() => {
                    const box = document.querySelector('div[role="textbox"][contenteditable="true"]');
                    if (!box) return 'removed';
                    return (box.innerText || '').trim();
                }""")
                if box_state == 'removed' or box_state == '':
                    is_submitted = True
                    break

            final_screenshot = await self.take_screenshot(prefix="after_reply")

            if not is_submitted:
                return {
                    "success": False,
                    "error": "Comment was not accepted by Threads (the reply textbox did not clear after clicking submit). Possible action block, temporary rate limit, or network error.",
                    "screenshot": final_screenshot or before_screenshot
                }

            return {
                "success": True,
                "screenshot": final_screenshot or before_screenshot,
                "message": "Comment successfully posted and confirmed on Threads"
            }

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Error posting reply to {thread_url}: {err_msg}")
            screenshot_path = await self.take_screenshot(prefix="reply_error")
            return {
                "success": False,
                "error": err_msg,
                "screenshot": screenshot_path
            }

    async def click(self, selector_or_text: str) -> str:
        if not self.page:
            return "Error: Browser not started"
        try:
            loc = self.page.locator(selector_or_text)
            if await loc.count() > 0:
                await loc.first.click(timeout=8000)
                await self.page.wait_for_timeout(2000)
                return f"Clicked: {selector_or_text}"

            text_loc = self.page.get_by_text(selector_or_text)
            if await text_loc.count() > 0:
                await text_loc.first.click(timeout=8000)
                await self.page.wait_for_timeout(2000)
                return f"Clicked text: '{selector_or_text}'"

            return f"Element not found: {selector_or_text}"
        except Exception as e:
            return f"Error clicking {selector_or_text}: {str(e)}"

    async def fill(self, selector_or_name: str, text: str) -> str:
        if not self.page:
            return "Error: Browser not started"
        try:
            loc = self.page.locator(selector_or_name)
            if await loc.count() > 0:
                await loc.first.click(timeout=6000)
                is_editable = await loc.first.is_editable()
                if is_editable:
                    await loc.first.fill(text)
                else:
                    await loc.first.type(text, delay=20)
                await self.page.wait_for_timeout(1000)
                return f"Filled '{selector_or_name}' with text."
            await self.page.keyboard.type(text, delay=20)
            return "Typed text into active element."
        except Exception as e:
            return f"Error filling {selector_or_name}: {str(e)}"

    async def take_screenshot(self, prefix: str = "step") -> str:
        """
        Takes a screenshot in memory as JPEG bytes and encodes it directly as a base64 Data URL.
        Stored directly in SQLite with ZERO raw files on disk.
        """
        if not self.page:
            return ""
        try:
            jpg_bytes = await self.page.screenshot(type="jpeg", quality=65, full_page=False)
            if not jpg_bytes:
                return ""
            b64 = base64.b64encode(jpg_bytes).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return ""
