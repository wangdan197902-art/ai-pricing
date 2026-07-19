"""Agnes LLM API 客户端封装。

基于 OpenAI 兼容协议调用 Agnes API（agnes-2.0-flash）。
- 重试 3 次，间隔 10 秒
- 超时 60 秒
- 缓存到 .cache/ 目录避免重复调用
- 暴露异常，不静默吞掉
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from openai import OpenAI
    from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError
except ImportError as exc:  # 暴露异常，由调用方决定如何处理
    raise ImportError(
        "未安装 openai SDK，请运行: pip install openai>=1.40.0"
    ) from exc


DEFAULT_API_KEY = "cpk-NfqJXKLc0SiZwn06FjQ414JWqmTCrh87Ht8MgcVjslCtKjai"
DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_MODEL = "agnes-2.0-flash"

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TIMEOUT = 60  # 秒
MAX_RETRIES = 3
RETRY_INTERVAL = 10  # 秒

# 项目根目录（scripts/lib/ 的上两级）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / ".cache" / "agnes"


class AgnesClient:
    """Agnes LLM API 客户端。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        enable_cache: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("AGNES_API_KEY") or DEFAULT_API_KEY
        self.base_url = base_url or os.environ.get("AGNES_BASE_URL") or DEFAULT_BASE_URL
        self.model = model or os.environ.get("AGNES_MODEL") or DEFAULT_MODEL
        self.enable_cache = enable_cache
        if enable_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=DEFAULT_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # 缓存工具
    # ------------------------------------------------------------------
    def _cache_key(self, payload: dict[str, Any]) -> Path:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{digest}.json"

    def _cache_get(self, payload: dict[str, Any]) -> str | None:
        if not self.enable_cache:
            return None
        path = self._cache_key(payload)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")).get("content")
            except (json.JSONDecodeError, OSError):
                # 缓存损坏，删除后重算
                path.unlink(missing_ok=True)
                return None
        return None

    def _cache_put(self, payload: dict[str, Any], content: str) -> None:
        if not self.enable_cache:
            return
        path = self._cache_key(payload)
        path.write_text(
            json.dumps({"content": content, "payload": payload}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 核心调用
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """OpenAI 兼容调用，含重试。

        失败 3 次后抛出最后一次异常（不静默吞掉）。
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        cached = self._cache_get(payload)
        if cached is not None:
            return cached

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.chat.completions.create(**payload)
                content = (resp.choices[0].message.content or "").strip()
                if not content:
                    raise ValueError("Agnes API 返回空内容")
                self._cache_put(payload, content)
                return content
            except (APIConnectionError, APITimeoutError, RateLimitError, APIError) as exc:
                last_exc = exc
                print(f"[Agnes] 第 {attempt}/{MAX_RETRIES} 次调用失败: {type(exc).__name__}: {exc}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_INTERVAL)
            except Exception as exc:  # 其他异常直接抛出
                raise RuntimeError(f"Agnes 调用异常: {type(exc).__name__}: {exc}") from exc

        # 重试用尽，暴露异常
        raise RuntimeError(
            f"Agnes API 重试 {MAX_RETRIES} 次后仍失败: {type(last_exc).__name__}: {last_exc}"
        )

    # ------------------------------------------------------------------
    # 高级封装
    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """生成内容。"""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str = "en",
    ) -> str:
        """翻译文本，保留 Markdown 结构。

        - target_lang: ISO 639-1 代码（zh/es/fr...）
        - 不翻译 front matter / 代码块
        """
        if not text.strip():
            return text
        if target_lang == source_lang:
            return text

        lang_names = {
            "en": "English", "zh": "Simplified Chinese (简体中文)",
            "es": "Spanish", "fr": "French", "de": "German",
            "ja": "Japanese", "ko": "Korean", "pt": "Portuguese",
            "ru": "Russian", "it": "Italian", "ar": "Arabic",
            "nl": "Dutch", "pl": "Polish", "tr": "Turkish",
            "vi": "Vietnamese", "th": "Thai", "id": "Indonesian",
            "sv": "Swedish", "no": "Norwegian", "da": "Danish",
        }
        target_name = lang_names.get(target_lang, target_lang)
        source_name = lang_names.get(source_lang, source_lang)

        system_prompt = (
            f"You are a professional translator. Translate the user's text from "
            f"{source_name} to {target_name}. "
            "Preserve all Markdown structure, headings, lists, code blocks, "
            "front matter delimiters (---), and HTML tags. "
            "Do not translate code, URLs, brand names (e.g. ChatGPT, Claude), "
            "or proper nouns. Output only the translated text, no explanations."
        )
        return self.generate(
            prompt=text,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=DEFAULT_MAX_TOKENS,
        )

    def translate_batch(
        self,
        items: Iterable[tuple[str, str, str]],
        max_workers: int = 5,
    ) -> list[str]:
        """并发翻译多个 (text, target_lang, source_lang) 元组。"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[str] = []
        items_list = list(items)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self.translate, text, tgt, src): idx
                       for idx, (text, tgt, src) in enumerate(items_list)}
            tmp: dict[int, str] = {}
            for future in as_completed(futures):
                idx = futures[future]
                tmp[idx] = future.result()
            for idx in range(len(items_list)):
                results.append(tmp[idx])
        return results


def get_default_client() -> AgnesClient:
    """获取默认客户端实例。"""
    return AgnesClient()


if __name__ == "__main__":
    # 简易自测：调用一次 API
    client = get_default_client()
    print("=== 测试 generate ===")
    print(client.generate("Say hello in 3 languages.", system_prompt="You are concise."))
    print("=== 测试 translate ===")
    print(client.translate("Hello world, this is a test.", "zh"))
