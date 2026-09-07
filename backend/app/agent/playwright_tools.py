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
    def __init__(
        self,
        headless: bool = True,
        imgbb_api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        self.headless = headless
        self.imgbb_api_key = imgbb_api_key
        self.proxy_url = proxy_url
        self.session_id = session_id
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
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ]

        launch_kwargs = {
            "headless": self.headless,
            "args": launch_args
        }
        if self.proxy_url and self.proxy_url.strip():
            launch_kwargs["proxy"] = {"server": self.proxy_url.strip()}
            logger.info(f"Launching Playwright with proxy: {self.proxy_url.strip()}")
        
        self.browser = await self.playwright.chromium.launch(**launch_kwargs)

        context_kwargs = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "locale": "id-ID",
            "timezone_id": "Asia/Jakarta",
            "geolocation": {"latitude": -6.2088, "longitude": 106.8456},
            "permissions": ["geolocation"],
            "extra_http_headers": {
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        }

        if self.session_file.exists():
            try:
                self.context = await self.browser.new_context(
                    storage_state=str(self.session_file),
                    **context_kwargs
                )
                logger.info("Loaded existing session from storage_state.json with Indonesian context")
            except Exception as e:
                logger.warning(f"Failed to load session file: {e}")
                self.context = await self.browser.new_context(**context_kwargs)
        else:
            self.context = await self.browser.new_context(**context_kwargs)

        # Inject sessionid cookie if provided
        if self.session_id and self.session_id.strip():
            clean_sid = self.session_id.strip()
            cookies = [
                {
                    "name": "sessionid",
                    "value": clean_sid,
                    "domain": ".threads.net",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
                {
                    "name": "sessionid",
                    "value": clean_sid,
                    "domain": ".threads.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
                {
                    "name": "sessionid",
                    "value": clean_sid,
                    "domain": ".instagram.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
            ]
            try:
                await self.context.add_cookies(cookies)
                logger.info("Successfully injected sessionid cookie into browser context")
            except Exception as e:
                logger.warning(f"Failed to inject sessionid cookie: {e}")

        self.page = await self.context.new_page()
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)
        await self._setup_modal_handlers(self.page)

    async def _setup_modal_handlers(self, page: Page):
        """
        Daftarkan interceptor otomatis (Playwright Locator Handlers).
        Kapan pun modal/dialog Threads muncul dan menghalangi interaksi,
        Playwright secara otomatis mendeteksi dan menutup modal tersebut,
        lalu melanjutkan proses yang sedang berjalan.
        """
        try:
            # 1. Tombol 'Not now' / 'Lain kali' / 'Batal' / 'Cancel'
            dismiss_buttons = page.locator(
                'button:has-text("Not now"), '
                'div[role="button"]:has-text("Not now"), '
                'button:has-text("Not Now"), '
                'div[role="button"]:has-text("Not Now"), '
                'button:has-text("Lain kali"), '
                'div[role="button"]:has-text("Lain kali"), '
                'button:has-text("Batal"), '
                'div[role="button"]:has-text("Batal"), '
                'button:has-text("Cancel"), '
                'div[role="button"]:has-text("Cancel"), '
                'button:has-text("Nanti saja"), '
                'div[role="button"]:has-text("Nanti saja")'
            )
            async def handle_dismiss_btn(loc):
                try:
                    logger.info("Auto-dismissing modal via Playwright locator handler (Dismiss button).")
                    await loc.click(timeout=2000)
                except Exception as ex:
                    logger.debug(f"Locator handler dismiss button exception: {ex}")

            await page.add_locator_handler(dismiss_buttons, handle_dismiss_btn)

            # 2. Tombol Close/Silang pada dialog (hindari textbox reply)
            close_buttons = page.locator(
                'div[role="dialog"]:not(:has(div[role="textbox"])) div[role="button"]:has(svg[aria-label="Close"]), '
                'div[role="dialog"]:not(:has(div[role="textbox"])) div[role="button"]:has(svg[aria-label="Tutup"]), '
                'div[role="dialog"]:not(:has(div[role="textbox"])) button:has(svg[aria-label="Close"]), '
                'div[role="dialog"]:not(:has(div[role="textbox"])) button:has(svg[aria-label="Tutup"])'
            )
            async def handle_close_btn(loc):
                try:
                    logger.info("Auto-dismissing modal via Playwright locator handler (Close SVG).")
                    await loc.click(timeout=2000)
                except Exception as ex:
                    logger.debug(f"Locator handler close button exception: {ex}")

            await page.add_locator_handler(close_buttons, handle_close_btn)

            # 3. Cookie / Legal Consent dialog
            cookie_buttons = page.locator(
                'div[role="button"]:has-text("Terima Semua"), '
                'div[role="button"]:has-text("Accept all"), '
                'button:has-text("Terima Semua"), '
                'button:has-text("Accept all")'
            )
            async def handle_cookie_btn(loc):
                try:
                    logger.info("Auto-dismissing cookie consent via Playwright locator handler.")
                    await loc.click(timeout=2000)
                except Exception as ex:
                    logger.debug(f"Locator handler cookie button exception: {ex}")

            await page.add_locator_handler(cookie_buttons, handle_cookie_btn)
            logger.info("Playwright locator handlers successfully registered for automated modal dismissal.")
        except Exception as e:
            logger.warning(f"Could not register modal locator handlers: {e}")

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
            try:
                await self.save_session()
            except Exception:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        self.context = None
        self.page = None

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

    async def dismiss_modals_if_present(self):
        """Helper proaktif untuk menutup modal/dialog penghalang seperti 'Save login info', 'Not now', dll."""
        if not self.page:
            return
        try:
            dismiss_selectors = [
                'div[role="dialog"] button:has-text("Not Now")',
                'div[role="dialog"] div[role="button"]:has-text("Not Now")',
                'div[role="dialog"] button:has-text("Not now")',
                'div[role="dialog"] div[role="button"]:has-text("Not now")',
                'div[role="dialog"] button:has-text("Lain kali")',
                'div[role="dialog"] div[role="button"]:has-text("Lain kali")',
                'div[role="dialog"] button:has-text("Cancel")',
                'div[role="dialog"] div[role="button"]:has-text("Cancel")',
                'div[role="dialog"] button:has-text("Batal")',
                'div[role="dialog"] div[role="button"]:has-text("Batal")',
                'div[role="dialog"] button:has-text("Close")',
                'div[role="dialog"] svg[aria-label="Close"]',
                'div[role="dialog"] svg[aria-label="Tutup"]',
                'div[role="button"]:has-text("Terima Semua")',
                'div[role="button"]:has-text("Accept all")'
            ]
            for selector in dismiss_selectors:
                btn = self.page.locator(selector)
                if await btn.count() > 0:
                    await btn.first.click(timeout=1500)
                    await self.page.wait_for_timeout(500)
                    logger.info(f"Dismissed modal overlay using selector: {selector}")

            # Fallback: jika masih ada modal dialog tanpa textbox komentar, tekan Escape
            generic_dialogs = self.page.locator('div[role="dialog"]:not(:has(div[role="textbox"]))')
            if await generic_dialogs.count() > 0:
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(300)
        except Exception:
            pass

    async def perform_fase1_login(self, username: str, password: str) -> Dict[str, Any]:
        """
        FASE 1: Khusus Login dengan Username & Password via https://www.threads.com/login.
        1. Buka browser baru khusus untuk proses login.
        2. Masuk ke https://www.threads.com/login.
        3. Isi username & password, lalu submit.
        4. Tunggu respon autentikasi hingga berhasil login.
        5. Simpan session ID / storage_state ke threads_session.json.
        6. TUTUP BROWSER SEPENUHNYA (stop proses browser).
        """
        if not username or not password:
            return {
                "success": False,
                "error": "Threads Username or Password has not been configured in Admin Settings."
            }

        playwright_instance = None
        login_browser = None
        login_context = None
        login_page = None
        screenshot = ""

        try:
            logger.info("[FASE 1] Membuka browser baru untuk login ke https://www.threads.com/login...")
            playwright_instance = await async_playwright().start()
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]
            launch_kwargs = {
                "headless": self.headless,
                "args": launch_args
            }
            if self.proxy_url and self.proxy_url.strip():
                launch_kwargs["proxy"] = {"server": self.proxy_url.strip()}
                logger.info(f"[FASE 1] Launching login browser with proxy: {self.proxy_url.strip()}")

            login_browser = await playwright_instance.chromium.launch(**launch_kwargs)
            login_context = await login_browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="id-ID",
                timezone_id="Asia/Jakarta",
                geolocation={"latitude": -6.2088, "longitude": 106.8456},
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
                }
            )
            login_page = await login_context.new_page()
            login_page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)
            await self._setup_modal_handlers(login_page)

            await login_page.goto("https://www.threads.com/login", wait_until="domcontentloaded", timeout=settings.BROWSER_TIMEOUT_MS)
            await login_page.wait_for_timeout(3500)
            await self.dismiss_modals_if_present()

            # Check if "Log in with username instead" or alternative prompt is present before inputs appear
            for _ in range(3):
                has_user_input = await login_page.locator('input[autocomplete="username"], input[name="username"], input[placeholder*="Username"], input[placeholder*="email"], input[type="text"]').count() > 0
                if has_user_input:
                    break

                alt_switch = login_page.locator(
                    'text="Log in with username instead", '
                    'text="Masuk dengan nama pengguna", '
                    'text="Log in with username", '
                    'div[role="button"]:has-text("username"), '
                    'button:has-text("username"), '
                    'a:has-text("username"), '
                    'span:has-text("username"), '
                    'span:has-text("Log in with")'
                )
                if await alt_switch.count() > 0:
                    logger.info("Found 'Log in with username instead' prompt. Clicking to reveal login fields...")
                    await alt_switch.first.click()
                    await login_page.wait_for_timeout(2000)
                else:
                    await login_page.wait_for_timeout(1000)

            # 1. Input username
            user_input = login_page.locator('input[autocomplete="username"], input[name="username"], input[placeholder*="Username"], input[placeholder*="email"], input[type="text"]').first
            if await user_input.count() > 0:
                await user_input.click()
                await user_input.fill(username)
            else:
                jpg = await login_page.screenshot(type="jpeg", quality=65)
                screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""
                return {
                    "success": False,
                    "error": "Username/email input field not found on https://www.threads.com/login.",
                    "screenshot": screenshot
                }

            # 2. Input password
            pass_input = login_page.locator('input[autocomplete="current-password"], input[type="password"], input[name="password"]').first
            if await pass_input.count() > 0:
                await pass_input.click()
                await pass_input.fill(password)
            else:
                jpg = await login_page.screenshot(type="jpeg", quality=65)
                screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""
                return {
                    "success": False,
                    "error": "Password input field not found on https://www.threads.com/login.",
                    "screenshot": screenshot
                }

            # 3. Submit login
            submit_btn = login_page.locator('input[type="submit"], button[type="submit"], div[role="button"]:has-text("Log in"), div[role="button"]:has-text("Masuk")')
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
            else:
                await pass_input.press("Enter")

            logger.info("[FASE 1] Form login disubmit. Menunggu respon autentikasi...")
            await login_page.wait_for_timeout(6000)

            # 4. Check for incorrect credentials error
            error_el = login_page.locator('div[role="alert"], p[role="alert"], div:has-text("Incorrect password"), div:has-text("Kata sandi salah"), div:has-text("Sorry, your password was incorrect"), div:has-text("Couldn\'t find your account")')
            if await error_el.count() > 0:
                err_text = (await error_el.first.inner_text()).strip()
                jpg = await login_page.screenshot(type="jpeg", quality=65)
                screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""
                return {
                    "success": False,
                    "error": f"Threads login rejected: {err_text or 'Incorrect username or password.'}",
                    "screenshot": screenshot
                }

            # 5. Check for 2FA / checkpoint
            if "checkpoint" in login_page.url or "challenge" in login_page.url:
                jpg = await login_page.screenshot(type="jpeg", quality=65)
                screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""
                return {
                    "success": False,
                    "error": f"Threads account requires additional security checkpoint (2FA/Challenge): {login_page.url}",
                    "screenshot": screenshot
                }

            # 6. Check if stuck on login
            has_pw = await login_page.locator('input[type="password"]').count() > 0
            if has_pw and "login" in login_page.url:
                jpg = await login_page.screenshot(type="jpeg", quality=65)
                screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""
                return {
                    "success": False,
                    "error": f"Login remained on login page ({login_page.url}). Please check credentials.",
                    "screenshot": screenshot
                }

            # 7. Login successful - wait 2 seconds for storage state / cookies to settle
            await login_page.wait_for_timeout(2000)

            # 8. Save storage state to file
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            await login_context.storage_state(path=str(self.session_file))
            logger.info(f"[FASE 1] Session state berhasil disimpan ke {self.session_file}.")

            jpg = await login_page.screenshot(type="jpeg", quality=65)
            screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""

            return {
                "success": True,
                "message": f"Phase 1 Success: Login succeeded and session ID saved to {self.session_file.name}. Browser closed.",
                "screenshot": screenshot
            }

        except Exception as e:
            logger.error(f"[FASE 1] Exception during login: {e}", exc_info=True)
            if login_page:
                try:
                    jpg = await login_page.screenshot(type="jpeg", quality=65)
                    screenshot = f"data:image/jpeg;base64,{base64.b64encode(jpg).decode('utf-8')}" if jpg else ""
                except Exception:
                    pass
            return {
                "success": False,
                "error": f"Exception during Phase 1 login: {str(e)}",
                "screenshot": screenshot
            }
        finally:
            # PENTING: TUTUP BROWSER FASE 1 SEPENUHNYA
            logger.info("[FASE 1] Menutup dan menghentikan browser login secara total...")
            if login_browser:
                try:
                    await login_browser.close()
                except Exception:
                    pass
            if playwright_instance:
                try:
                    await playwright_instance.stop()
                except Exception:
                    pass

    async def ensure_threads_login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Arsitektur Dua Fase:
        - FASE 1 (Login via /login):
          Hanya dijalankan jika session file belum ada atau sudah expired.
          Browser login dibuka, mengisi username & password, menyimpan session ID,
          kemudian browser login DITUTUP SEPENUHNYA.
        - FASE 2 (Eksekusi dengan Session ID Tanpa /login):
          Membuka browser baru yang langsung memuat file session ID.
          Langsung membuka https://www.threads.com (TIDAK membuka /login).
          Karena dibuka dari sesi tersimpan, modal wizard post-login tidak akan muncul
          sehingga tombol reply terlihat jelas dan bebas halangan.
        """
        try:
            has_session_source = bool(self.session_id and self.session_id.strip()) or self.session_file.exists()

            # 1. Fase 1 hanya jika TIDAK ADA session_id dan TIDAK ADA session_file
            if not has_session_source:
                logger.info("[FASE 1] No session ID or session file found. Running Fase 1 login via /login...")
                await self.close()
                f1_res = await self.perform_fase1_login(username, password)
                if not f1_res.get("success"):
                    return f1_res

            # 2. FASE 2: Jalankan browser dengan Session ID / session file (Tanpa masuk ke /login)
            logger.info("[FASE 2] Membuka browser dengan Session ID tersimpan (tanpa /login)...")
            if not self.page:
                await self.start()

            # Buka langsung ke https://www.threads.net (FEED UTAMA, BUKAN /login)
            await self.navigate("https://www.threads.net")
            await self.page.wait_for_timeout(3500)
            await self.dismiss_modals_if_present()

            # Verifikasi status sesi di Fase 2
            has_password_field = await self.page.locator('input[type="password"], input[autocomplete="current-password"]').count() > 0
            has_login_button = await self.page.locator('a[href*="/login"], button:has-text("Log in"), button:has-text("Masuk")').count() > 0
            is_login_page = "login" in self.page.url or has_password_field

            # Jika ternyata sesi tidak valid / expired
            if is_login_page or (has_login_button and not await self.page.locator('div[role="textbox"], a[href*="/@"]').count()):
                if self.session_id and self.session_id.strip():
                    ss = await self.take_screenshot(prefix="invalid_sessionid")
                    return {
                        "success": False,
                        "error": "The configured Threads sessionID cookie is expired or invalid. Please copy a fresh sessionid from your browser (F12 > Application > Cookies) and update Admin Settings.",
                        "screenshot": ss
                    }

                logger.warning("[FASE 2] Sesi file tersimpan ternyata sudah expired/logout. Mengulang Fase 1...")
                await self.close()
                self.session_file.unlink(missing_ok=True)

                # Jalankan ulang Fase 1 jika ada username/password
                f1_res = await self.perform_fase1_login(username, password)
                if not f1_res.get("success"):
                    return f1_res

                # Jalankan ulang Fase 2
                logger.info("[FASE 2] Membuka kembali browser dengan session baru...")
                await self.start()
                await self.navigate("https://www.threads.net")
                await self.page.wait_for_timeout(3500)
                await self.dismiss_modals_if_present()

                if "login" in self.page.url or await self.page.locator('input[type="password"]').count() > 0:
                    ss = await self.take_screenshot(prefix="fase2_failed")
                    return {
                        "success": False,
                        "error": "Phase 2 failed to validate session after re-login.",
                        "screenshot": ss
                    }

            # Sesi aktif terkonfirmasi di Fase 2 -> simpan session state
            await self.save_session()
            ss = await self.take_screenshot(prefix="fase2_active_session")
            logger.info(f"[FASE 2] Sesi aktif dan valid di {self.page.url}. Siap lanjut tanpa modal post-login.")
            return {
                "success": True,
                "message": f"Phase 2 active using session ID ({self.page.url}) without opening login page.",
                "screenshot": ss
            }

        except Exception as e:
            logger.error(f"Error pada proses autentikasi Threads: {e}", exc_info=True)
            ss = await self.take_screenshot(prefix="auth_error")
            return {
                "success": False,
                "error": f"Exception during Threads authentication: {str(e)}",
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
            await self.dismiss_modals_if_present()

            js_scanner = """
            () => {
                function parseCount(str) {
                    if (!str) return 0;
                    str = str.toLowerCase().trim();
                    let multiplier = 1;
                    if (str.includes('k') || str.includes('rb')) {
                        multiplier = 1000;
                        str = str.replace(',', '.');
                        const m = str.match(/([0-9]+(?:\\.[0-9]+)?)/);
                        return m ? Math.round(parseFloat(m[1]) * multiplier) : 0;
                    }
                    if (str.includes('m') || str.includes('jt')) {
                        multiplier = 1000000;
                        str = str.replace(',', '.');
                        const m = str.match(/([0-9]+(?:\\.[0-9]+)?)/);
                        return m ? Math.round(parseFloat(m[1]) * multiplier) : 0;
                    }
                    const digits = str.replace(/[^0-9]/g, '');
                    return digits ? parseInt(digits, 10) : 0;
                }

                const results = [];
                const origin = window.location.origin || 'https://www.threads.com';
                let containers = Array.from(document.querySelectorAll('div[data-pressable-container="true"], article, div[role="article"]'));
                if (containers.length === 0) {
                    const postLinks = document.querySelectorAll('a[href*="/post/"], a[href*="/t/"]');
                    containers = Array.from(postLinks).map(a => a.closest('div[role="article"], article, div[data-pressable-container="true"]') || a.parentElement?.parentElement).filter(Boolean);
                }
                
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

            all_feed_threads = []
            for scroll_step in range(max_scrolls):
                batch = await self.page.evaluate(js_scanner)
                for item in batch:
                    u = item["url"]
                    if u not in commented_urls:
                        if not any(v["url"] == u for v in all_feed_threads):
                            all_feed_threads.append(item)
                        if item["comment_count"] >= min_comments or item["like_count"] >= min_likes:
                            if not any(v["url"] == u for v in viral_threads):
                                viral_threads.append(item)

                # Scroll down to load more items
                await self.page.evaluate("window.scrollBy(0, 1200)")
                await self.page.wait_for_timeout(2000)

            # Sort both lists descending by engagement score (comments weighted higher)
            viral_threads.sort(key=lambda x: (x.get("comment_count", 0) * 2 + x.get("like_count", 0)), reverse=True)
            all_feed_threads.sort(key=lambda x: (x.get("comment_count", 0) * 2 + x.get("like_count", 0)), reverse=True)

            if viral_threads:
                logger.info(f"Found {len(viral_threads)} viral threads matching criteria (>= {min_comments} comments OR >= {min_likes} likes).")
                return viral_threads
            elif all_feed_threads:
                logger.warning(f"No thread met the strict criteria (>={min_comments} comments or >={min_likes} likes). Falling back to top {len(all_feed_threads)} most active threads in feed.")
                return all_feed_threads
            else:
                logger.warning("No posts could be extracted from the Threads feed.")
                return []

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
            await self.dismiss_modals_if_present()

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
                "thread_url": thread_url,
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
