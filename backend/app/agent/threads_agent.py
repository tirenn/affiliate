import json
import random
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Product, PostLog, AgentStepLog, SystemSetting, CommentedThread
from app.agent.playwright_tools import PlaywrightToolManager
from app.agent.llm_client import LLMClient

logger = logging.getLogger("threads_agent.coordinator")


async def get_system_setting(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting and setting.value is not None else default


def is_ai_quota_error(error_msg: Optional[str]) -> bool:
    """Mendeteksi apakah error disebabkan oleh limit kuota, rate limit, atau token habis pada API AI."""
    if not error_msg:
        return False
    msg = str(error_msg).lower()
    quota_indicators = [
        "429",
        "402",
        "rate limit",
        "quota",
        "credit",
        "insufficient_quota",
        "resource_exhausted",
        "exceeded your current quota",
        "out of credits",
        "balance",
        "tokens limit",
        "payment required"
    ]
    return any(indicator in msg for indicator in quota_indicators)


class ThreadsAgentRunner:
    def __init__(self, db: AsyncSession, scheduler: Optional[Any] = None, is_cron: bool = False):
        self.db = db
        self.scheduler = scheduler
        self.is_cron = is_cron
        self.browser_manager: Optional[PlaywrightToolManager] = None
        self.llm_client: Optional[LLMClient] = None
        self.post_log: Optional[PostLog] = None

    async def execute(self) -> Dict[str, Any]:
        """
        Alur Eksekusi:
        1. Ambil setting (OpenRouter key/model, Threads login, min comments).
        2. Buka Threads, cek login.
        3. Scan feed untuk mencari thread viral dengan komentar >= min_comments yang belum pernah dikomentari.
        4. Pilih 1 thread viral secara random.
        5. Ambil produk yang belum terpost (is_posted=False). Jika semua sudah terpost, reset siklus antrean.
        6. AI membaca konteks thread viral dan mencocokkan produk Shopee yang relevan (atau random jika tidak ada yg cocok), lalu membuat komentar menarik dengan Link Komisi Ekstra.
        7. Posting komentar balasan ke thread viral tersebut via Playwright.
        8. Catat thread ke CommentedThread (agar tidak dispam lagi), tandai produk is_posted=True, dan simpan log detail.
        """
        # 1. Ambil Setting murni dari database system_settings (tanpa fallback env)
        openrouter_key = await get_system_setting(self.db, "openrouter_api_key", "")
        openrouter_model = await get_system_setting(self.db, "openrouter_model", "openrouter/free")
        threads_username = await get_system_setting(self.db, "threads_username", "")
        threads_password = await get_system_setting(self.db, "threads_password", "")
        min_comments_str = await get_system_setting(self.db, "min_thread_comments", "50")
        min_comments = int(min_comments_str) if min_comments_str.isdigit() else 50
        min_likes_str = await get_system_setting(self.db, "min_thread_likes", "100")
        min_likes = int(min_likes_str) if min_likes_str.isdigit() else 100
        headless_str = await get_system_setting(self.db, "headless_browser", "true")
        headless = headless_str.lower() == "true"
        proxy_url = await get_system_setting(self.db, "proxy_url", "")
        threads_session_id = await get_system_setting(self.db, "threads_session_id", "")

        # 2. Ambil list thread yang sudah pernah dikomentari
        commented_res = await self.db.execute(select(CommentedThread.thread_url))
        already_commented_urls = set(commented_res.scalars().all())

        # 3. Ambil daftar produk yang belum terpost (is_posted == False)
        cand_res = await self.db.execute(
            select(Product).where(Product.is_posted == False).order_by(Product.post_count.asc(), Product.id.asc()).limit(30)
        )
        candidates = cand_res.scalars().all()

        # Aturan Siklus: Jika semua produk sudah terpost, reset is_posted ke False!
        if not candidates:
            total_prods_res = await self.db.execute(select(func.count(Product.id)))
            total_prods = total_prods_res.scalar_one()
            if total_prods > 0:
                logger.info("Semua produk telah diposting. Mereset siklus antrean agar dapat dipost kembali...")
                await self.db.execute(update(Product).values(is_posted=False))
                await self.db.commit()
                cand_res = await self.db.execute(
                    select(Product).where(Product.is_posted == False).order_by(Product.post_count.asc(), Product.id.asc()).limit(30)
                )
                candidates = cand_res.scalars().all()

        if not candidates:
            raise ValueError("No products found in database. Please upload a Shopee products CSV file first.")

        # 4. Initialize initial PostLog
        self.post_log = PostLog(
            product_name="Scanning Viral Threads...",
            affiliate_url="",
            status="running",
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(self.post_log)
        await self.db.commit()
        await self.db.refresh(self.post_log)

        screenshot_file = None

        try:
            # 5. Initialize Browser & LLM
            self.browser_manager = PlaywrightToolManager(
                headless=headless,
                proxy_url=proxy_url,
                session_id=threads_session_id
            )
            self.llm_client = LLMClient(api_key=openrouter_key, model=openrouter_model)

            # ----------------------------------------------------
            # STEP 1: Two-Phase Authentication & Session Check
            # ----------------------------------------------------
            logger.info("[STEP 1/4] Starting Threads authentication (Phase 1: Login & Save Session, Phase 2: Run with Session ID)...")
            step1_thought = "Executing session authentication: using browser sessionID cookie or saved session state without visiting /login."
            step1_args = json.dumps({
                "mode": "SessionID Cookie" if threads_session_id else "Session File / Credentials",
                "username": threads_username or "(not set)"
            })

            login_res = await self.browser_manager.ensure_threads_login(threads_username, threads_password)
            step1_screenshot = login_res.get("screenshot")

            if not login_res.get("success"):
                err_reason = login_res.get("error", "Threads login failed")
                await self.record_step(
                    step_number=1,
                    tool_name="login",
                    thought=step1_thought,
                    tool_arguments=step1_args,
                    tool_output=f"FAILED: {err_reason}",
                    screenshot_path=step1_screenshot
                )
                return await self._finalize_log(
                    status="failed",
                    error=f"Failed at step [login]: {err_reason}",
                    screenshot=step1_screenshot
                )

            await self.record_step(
                step_number=1,
                tool_name="login",
                thought=step1_thought,
                tool_arguments=step1_args,
                tool_output=f"SUCCESS: {login_res.get('message', 'Login successful / session active.')}",
                screenshot_path=step1_screenshot
            )

            # ----------------------------------------------------
            # STEP 2: find viral threads
            # ----------------------------------------------------
            logger.info(f"[STEP 2/4] Scanning for viral threads (min {min_comments} comments OR {min_likes} likes)...")
            step2_thought = f"Scanning Threads feed for viral threads with at least {min_comments} comments OR {min_likes} likes that haven't been commented on yet."
            step2_args = json.dumps({
                "min_comments": min_comments,
                "min_likes": min_likes,
                "already_commented_count": len(already_commented_urls),
                "max_scrolls": 4
            })

            viral_threads = await self.browser_manager.find_viral_threads(
                min_comments=min_comments,
                min_likes=min_likes,
                commented_urls=already_commented_urls,
                max_scrolls=5
            )

            if not viral_threads:
                # Tolerant fallback: grab top active posts from feed
                fallback_threads = await self.browser_manager.find_viral_threads(
                    min_comments=0,
                    min_likes=0,
                    commented_urls=already_commented_urls,
                    max_scrolls=3
                )
                if fallback_threads:
                    viral_threads = fallback_threads

            if not viral_threads:
                step2_ss = await self.browser_manager.take_screenshot(prefix="no_viral_threads")
                err_reason = f"No active threads found in feed. Please verify that Threads feed is reachable."
                await self.record_step(
                    step_number=2,
                    tool_name="find_viral_threads",
                    thought=step2_thought,
                    tool_arguments=step2_args,
                    tool_output=f"FAILED: {err_reason}",
                    screenshot_path=step2_ss
                )
                return await self._finalize_log(
                    status="failed",
                    error=f"Failed at step [find_viral_threads]: {err_reason}",
                    screenshot=step2_ss
                )

            # Pick from top 3 most engaging viral threads
            target_thread = random.choice(viral_threads[:min(3, len(viral_threads))])
            self.post_log.target_thread_url = target_thread["url"]
            self.post_log.threads_post_url = target_thread["url"]
            self.post_log.target_thread_snippet = target_thread["text"]
            await self.db.commit()

            criteria_met = []
            if target_thread.get("comment_count", 0) >= min_comments:
                criteria_met.append(f"{target_thread.get('comment_count')} comments (>= {min_comments})")
            if target_thread.get("like_count", 0) >= min_likes:
                criteria_met.append(f"{target_thread.get('like_count')} likes (>= {min_likes})")
            criteria_str = ", ".join(criteria_met) if criteria_met else f"{target_thread.get('comment_count', 0)} comments, {target_thread.get('like_count', 0)} likes"

            step2_output = (
                f"SUCCESS: Found {len(viral_threads)} viral threads meeting criteria (>= {min_comments} comments OR >= {min_likes} likes). "
                f"Selected post by @{target_thread.get('author', 'user')} [Matched Criteria: {criteria_str}].\n"
                f"URL: {target_thread['url']}\n"
                f"Snippet: {target_thread['text'][:200]}"
            )
            await self.record_step(
                step_number=2,
                tool_name="find_viral_threads",
                thought=step2_thought,
                tool_arguments=step2_args,
                tool_output=step2_output,
                screenshot_path=None
            )

            # ----------------------------------------------------
            # STEP 3: generate post
            # ----------------------------------------------------
            logger.info("[STEP 3/4] Generating AI affiliate comment via OpenRouter...")
            step3_thought = "Analyzing viral thread context and matching with the most relevant Shopee product to compose engaging Indonesian comment with Extra Commission link."
            step3_args = json.dumps({
                "model": openrouter_model,
                "candidate_count": len(candidates),
                "target_thread": target_thread['url']
            })

            if not openrouter_key:
                err_reason = "OpenRouter API Key is not set in Admin Settings. Please configure your API Key."
                await self.record_step(
                    step_number=3,
                    tool_name="generate_post",
                    thought=step3_thought,
                    tool_arguments=step3_args,
                    tool_output=f"FAILED: {err_reason}"
                )
                return await self._finalize_log(
                    status="failed",
                    error=f"Failed at step [generate_post]: {err_reason}",
                    screenshot=None
                )

            product_dicts = []
            for p in candidates:
                product_dicts.append({
                    "id": p.id,
                    "name": p.product_name,
                    "price": p.price,
                    "commission": p.commission_amount or p.commission_rate,
                    "extra_link": p.extra_commission_url or p.affiliate_url,
                    "link": p.affiliate_url
                })

            try:
                match_result = await self.llm_client.match_and_craft_reply(
                    thread_text=target_thread["text"],
                    products=product_dicts
                )
                chosen_prod_id = match_result.get("selected_product_id")
                comment_text = match_result.get("comment_text", "").strip()
                match_reason = match_result.get("reason", "")

                chosen_product = next((p for p in candidates if p.id == chosen_prod_id), candidates[0])
                primary_affiliate_link = chosen_product.extra_commission_url or chosen_product.affiliate_url

                if primary_affiliate_link and primary_affiliate_link not in comment_text:
                    comment_text = f"{comment_text} 👉 {primary_affiliate_link}"

                self.post_log.product_id = chosen_product.id
                self.post_log.product_name = chosen_product.product_name
                self.post_log.affiliate_url = chosen_product.affiliate_url
                self.post_log.extra_commission_url = chosen_product.extra_commission_url
                self.post_log.post_text = comment_text
                await self.db.commit()

                step3_output = (
                    f"SUCCESS: Selected product: '{chosen_product.product_name}' (Commission: {chosen_product.commission_amount or chosen_product.commission_rate or '-'}).\n"
                    f"Relevance Reason: {match_reason}\n"
                    f"Extra Commission Link: {primary_affiliate_link}\n\n"
                    f"Generated Indonesian Comment:\n\"{comment_text}\""
                )
                await self.record_step(
                    step_number=3,
                    tool_name="generate_post",
                    thought=step3_thought,
                    tool_arguments=step3_args,
                    tool_output=step3_output
                )
            except Exception as e:
                err_reason = f"Failed to generate comment from OpenRouter AI: {str(e)}"
                is_quota = is_ai_quota_error(str(e))
                already_in_quota_limit = bool(self.scheduler and getattr(self.scheduler, "ai_quota_exceeded", False))

                # Jika cron dan kuota AI masih limit pada proses berikutnya -> TIDAK PERLU DI-LOG KE DATABASE!
                if self.is_cron and is_quota and already_in_quota_limit:
                    logger.warning(
                        f"[CRON QUOTA THROTTLED] AI quota limit still active: {str(e)}. "
                        "Skipping database log entry per quota throttle policy until quota recovers."
                    )
                    if self.browser_manager:
                        await self.browser_manager.close()
                    if self.post_log:
                        await self.db.delete(self.post_log)
                        await self.db.commit()
                    return {
                        "status": "throttled_quota_limit",
                        "error": err_reason,
                        "post_log_id": None
                    }

                # Jika ini pertama kali kena quota limit saat cron -> catat ke DB dan tandai flag
                if self.scheduler and is_quota:
                    self.scheduler.ai_quota_exceeded = True
                    logger.warning(
                        f"[CRON QUOTA LIMIT DETECTED] First occurrence of AI quota limit logged to DB: {str(e)}. "
                        "Subsequent quota errors will be throttled until recovery."
                    )

                await self.record_step(
                    step_number=3,
                    tool_name="generate_post",
                    thought=step3_thought,
                    tool_arguments=step3_args,
                    tool_output=f"FAILED: {err_reason}"
                )
                return await self._finalize_log(
                    status="failed",
                    error=f"Failed at step [generate_post]: {err_reason}",
                    screenshot=None
                )

            # ----------------------------------------------------
            # STEP 4: posting
            # ----------------------------------------------------
            logger.info(f"[STEP 4/4] Sending reply to {target_thread['url']}...")
            step4_thought = f"Visiting viral thread {target_thread['url']}, inserting AI comment and submitting reply to Threads."
            step4_args = json.dumps({"target_url": target_thread["url"], "comment_length": len(comment_text)})

            reply_result = await self.browser_manager.reply_to_thread(
                thread_url=target_thread["url"],
                comment_text=comment_text
            )

            step4_screenshot = reply_result.get("screenshot")

            if not reply_result.get("success"):
                err_reason = reply_result.get("error", "Failed to post reply to Threads")
                await self.record_step(
                    step_number=4,
                    tool_name="post_reply",
                    thought=step4_thought,
                    tool_arguments=step4_args,
                    tool_output=f"FAILED: {err_reason}",
                    screenshot_path=step4_screenshot
                )
                return await self._finalize_log(
                    status="failed",
                    error=f"Failed at step [post_reply]: {err_reason}",
                    screenshot=step4_screenshot
                )

            # Record thread to CommentedThread (Anti-Spam)
            new_commented = CommentedThread(
                thread_url=target_thread["url"],
                thread_author=target_thread.get("author"),
                thread_snippet=target_thread.get("text"),
                comment_count_found=target_thread.get("comment_count", 0),
                like_count_found=target_thread.get("like_count", 0),
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(new_commented)

            # Mark product as posted
            chosen_product.is_posted = True
            chosen_product.post_count = (chosen_product.post_count or 0) + 1
            chosen_product.last_posted_at = datetime.now(timezone.utc)
            chosen_product.status = "posted"

            # Set thread link for direct manual verification in new tab
            posted_thread_url = reply_result.get("thread_url") or target_thread["url"]
            self.post_log.threads_post_url = posted_thread_url
            self.post_log.target_thread_url = posted_thread_url
            await self.db.commit()

            step4_output = f"SUCCESS: Reply successfully published to thread {posted_thread_url}!\nScreenshot captured."
            await self.record_step(
                step_number=4,
                tool_name="post_reply",
                thought=step4_thought,
                tool_arguments=step4_args,
                tool_output=step4_output,
                screenshot_path=step4_screenshot
            )

            # Reset ai_quota_exceeded flag on successful post
            if self.scheduler:
                if getattr(self.scheduler, "ai_quota_exceeded", False):
                    logger.info("AI Quota limit has recovered! Normal DB logging resumed.")
                self.scheduler.ai_quota_exceeded = False

            return await self._finalize_log(
                status="success",
                error=None,
                screenshot=step4_screenshot
            )

        except Exception as e:
            logger.error(f"Unexpected error in ThreadsAgentRunner: {e}", exc_info=True)
            is_quota = is_ai_quota_error(str(e))
            already_in_quota_limit = bool(self.scheduler and getattr(self.scheduler, "ai_quota_exceeded", False))

            if self.is_cron and is_quota and already_in_quota_limit:
                logger.warning(f"[CRON QUOTA THROTTLED] Skipping DB log for subsequent quota error: {e}")
                if self.browser_manager:
                    await self.browser_manager.close()
                if self.post_log:
                    await self.db.delete(self.post_log)
                    await self.db.commit()
                return {
                    "status": "throttled_quota_limit",
                    "error": str(e),
                    "post_log_id": None
                }

            if self.scheduler and is_quota:
                self.scheduler.ai_quota_exceeded = True

            return await self._finalize_log(
                status="failed",
                error=f"Unexpected error: {str(e)}",
                screenshot=None
            )

    async def record_step(
        self,
        step_number: int,
        tool_name: str,
        thought: str,
        tool_arguments: Optional[str] = None,
        tool_output: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ) -> AgentStepLog:
        step = AgentStepLog(
            post_log_id=self.post_log.id,
            step_number=step_number,
            tool_name=tool_name,
            thought=thought,
            tool_arguments=tool_arguments,
            tool_output=tool_output,
            screenshot_path=screenshot_path,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(step)
        await self.db.commit()
        await self.db.refresh(step)
        return step

    async def _finalize_log(
        self,
        status: str,
        error: Optional[str] = None,
        screenshot: Optional[str] = None
    ) -> Dict[str, Any]:
        if self.browser_manager:
            if not screenshot:
                screenshot = await self.browser_manager.take_screenshot(prefix="final")
            await self.browser_manager.close()

        self.post_log.status = status
        self.post_log.error_message = error
        if screenshot:
            self.post_log.final_screenshot = screenshot
        self.post_log.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        return {
            "status": status,
            "post_log_id": self.post_log.id,
            "error": error
        }
