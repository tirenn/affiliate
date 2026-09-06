import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("threads_agent.llm")

# Standard tool definitions
AGENT_TOOLS = [
    {
        "name": "browser_navigate",
        "description": "Navigate the browser to a specific URL (e.g., 'https://www.threads.net' or 'https://www.threads.net/login')",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The destination URL"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_click",
        "description": "Click on an element on the webpage using a CSS selector or visible button text",
        "parameters": {
            "type": "object",
            "properties": {
                "selector_or_text": {
                    "type": "string",
                    "description": "CSS selector, button name, or visible text to click"
                }
            },
            "required": ["selector_or_text"]
        }
    },
    {
        "name": "browser_fill",
        "description": "Fill an input field, textarea, or contenteditable editor with text",
        "parameters": {
            "type": "object",
            "properties": {
                "selector_or_name": {
                    "type": "string",
                    "description": "Selector, placeholder, or name of the field to type into"
                },
                "text": {
                    "type": "string",
                    "description": "The text content to input"
                }
            },
            "required": ["selector_or_name", "text"]
        }
    },
    {
        "name": "browser_press_key",
        "description": "Press a keyboard key like 'Enter', 'Tab', or 'Escape'",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to press, e.g. 'Enter'"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "browser_wait",
        "description": "Wait for a specified number of seconds (between 1 and 10 seconds) for UI updates",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "number", "description": "Seconds to wait"}
            },
            "required": ["seconds"]
        }
    },
    {
        "name": "browser_get_page_summary",
        "description": "Inspect the webpage to get current URL, title, and a list of visible buttons, inputs, and interactive elements",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "browser_take_screenshot",
        "description": "Take a screenshot of the current page for logging and verification",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "finish_post",
        "description": "Call this tool once the post is published to Threads or if the run permanently fails",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["success", "failed"],
                    "description": "Outcome of the post"
                },
                "post_url": {
                    "type": "string",
                    "description": "URL of the created post on Threads if available"
                },
                "summary": {
                    "type": "string",
                    "description": "Summary of actions taken and final result"
                }
            },
            "required": ["status", "summary"]
        }
    }
]


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or ""
        self.model = model or "openrouter/free"
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")

    async def step(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute one step with OpenRouter chat completions and return:
        {
            "thought": str,
            "tool_calls": [{"name": str, "args": dict}]
        }
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://threads-affiliate.bot",
            "X-Title": "Threads Affiliate Bot",
            "Content-Type": "application/json"
        }

        openai_tools = [
            {"type": "function", "function": t} for t in AGENT_TOOLS
        ]

        # Convert internal messages to OpenAI-compatible chat format
        formatted_messages = []
        for m in messages:
            role = m.get("role")
            if role in ["system", "user"]:
                formatted_messages.append({"role": role, "content": m.get("content", "")})
            elif role == "assistant":
                msg = {"role": "assistant", "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {
                            "id": f"call_{idx}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("args", {}))
                            }
                        }
                        for idx, tc in enumerate(m["tool_calls"])
                    ]
                formatted_messages.append(msg)
            elif role == "tool":
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", "call_0"),
                    "content": str(m.get("content", ""))
                })

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "tools": openai_tools,
            "tool_choice": "auto"
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                error_body = resp.text
                logger.error(f"OpenRouter API Error {resp.status_code}: {error_body}")
                raise RuntimeError(f"OpenRouter API Error {resp.status_code}: {error_body}")
            data = resp.json()

        choice = data["choices"][0]["message"]
        thought = choice.get("content") or ""
        tool_calls = []

        # 1. Standard OpenAI function calling format
        if choice.get("tool_calls"):
            for tc in choice["tool_calls"]:
                func = tc.get("function", {})
                args_raw = func.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "name": func.get("name", ""),
                    "args": args
                })

        # 2. Fallback heuristic: If free model returns JSON in content text instead of tool_calls
        if not tool_calls and "{" in thought and ("browser_" in thought or "finish_post" in thought):
            try:
                # Attempt to extract JSON tool call block if present in thought
                start_idx = thought.find("{")
                end_idx = thought.rfind("}") + 1
                candidate = json.loads(thought[start_idx:end_idx])
                if "name" in candidate and ("browser_" in candidate["name"] or candidate["name"] == "finish_post"):
                    tool_calls.append({
                        "name": candidate["name"],
                        "args": candidate.get("args") or candidate.get("parameters") or {}
                    })
            except Exception:
                pass

        return {"thought": thought.strip(), "tool_calls": tool_calls}

    async def match_and_craft_reply(
        self,
        thread_text: str,
        products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        AI menganalisis konteks thread viral dan mencocokkan produk Shopee affiliate yang relevan.
        Menghasilkan komentar yang persuasif dan natural dengan Link Komisi Ekstra.
        """
        if not products:
            raise ValueError("No candidate products provided for matching")

        product_summaries = []
        for p in products:
            link = p.get("extra_link") or p.get("link") or ""
            product_summaries.append(
                f"- ID: {p['id']} | Nama: {p['name']} | Harga: {p.get('price') or '-'} | Komisi: {p.get('commission') or '-'} | Link: {link}"
            )
        products_str = "\n".join(product_summaries)

        system_prompt = """Kamu adalah copywriter affiliate expert di Meta Threads Indonesia.
Tugasmu:
1. Baca konteks/isi postingan thread viral yang sedang ramai dibicarakan.
2. Evaluasi daftar produk affiliate Shopee yang tersedia.
3. Pilih 1 produk yang PALING COCOK / RELEVAN dengan konteks obrolan thread tersebut.
   - Contoh: thread seputar makanan pedas, kuliner, lapar -> pilih Baso Aci / cemilan.
   - Contoh: thread seputar outfit, fashion, gaya, baju -> pilih Rok Span / busana.
   - JIKA TIDAK ADA produk yang cocok dengan konteks thread, pilih 1 produk secara RANDOM.
4. Buat 1 KOMENTAR balasan Threads yang:
   - Bahasa Indonesia gaul/santai, relatable, tidak kaku (hindari bahasa iklan robotik/spam!).
   - Berikan sentuhan rekomendasi yang membuat orang penasaran dan ingin beli.
   - Sertakan Link Komisi Ekstra dari produk yang dipilih.

Wajib berikan output HANYA format JSON valid berikut:
{
  "selected_product_id": <id_produk_angka>,
  "reason": "<alasan pemilihan produk>",
  "comment_text": "<isi komentar balasan Threads yang mengandung link komisi ekstra>"
}"""

        user_content = f"""Konteks Thread Viral:
\"\"\"{thread_text}\"\"\"

Daftar Produk Pilihan:
{products_str}

Pilihlah 1 produk terbaik dan buat komentar balasan Threads dalam format JSON."""

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://threads-affiliate.bot",
            "X-Title": "Threads Affiliate Bot",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter API Error {resp.status_code}: {resp.text}")
            data = resp.json()

        raw_reply = data["choices"][0]["message"]["content"]
        start_idx = raw_reply.find("{")
        end_idx = raw_reply.rfind("}") + 1

        if start_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(raw_reply[start_idx:end_idx])
            except Exception:
                pass

        default_prod = products[0]
        link = default_prod.get("extra_link") or default_prod.get("link") or ""
        return {
            "selected_product_id": default_prod["id"],
            "reason": "Fallback random product",
            "comment_text": f"Bener banget kak! Buat yg lagi butuh rekomen ini bagus bgt: {link}"
        }
