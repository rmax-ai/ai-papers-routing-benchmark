"""Provider requests with per-attempt persistence and table-computed costs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ROOT = Path.cwd()
RAW = ROOT / "raw"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
JEV_URL = "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"
MODELS = {
    "deepseek": "deepseek-flash",
    "openai": "gpt-6-luna",
    "gemini_requested": "gemini-3.5-flash-lite",
    "jev": "typesafe-ai/jev",
}
PRICES = {
    "openai": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
    "deepseek_offpeak": {"input": 0.15, "cached_input": 0.003, "output": 0.60},
    "deepseek_peak": {"input": 0.30, "cached_input": 0.006, "output": 1.20},
    "gemini": {"input": 0.30, "cached_input": 0.30, "output": 2.50},
    "jev": {"input": 0.042, "cached_input": 0.042, "output": 0.0},
}
RATE_SOURCES = {
    "openai": "https://developers.openai.com/api/docs/models/gpt-6-luna; prior-art compare.ts reviewed 2026-09-24 UTC",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing/; prior-art compare.ts constants reviewed 2026-09-24 UTC",
    "gemini": "video-summarization/scripts/summarize_video.py PRICING_PER_MILLION; prior-art reviewed 2026-09-25 UTC",
    "jev": "prior-art compare.ts reviewed fallback $0.042/1M input, $0 output; live table not queried",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_string(value: datetime | None = None) -> str:
    return (value or now_utc()).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def secret_values() -> list[str]:
    return [os.environ.get(k, "") for k in (
        "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "AI_GATEWAY_API_KEY"
    ) if os.environ.get(k)]


def sanitize(value: str) -> str:
    for secret in secret_values():
        value = value.replace(secret, "[redacted]")
    home = str(Path.home())
    value = value.replace(home, "~")
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[redacted]", value)
    value = re.sub(r"(?i)([?&]key=)[^&\s]+", r"\1[redacted]", value)
    value = re.sub(r'(?i)("request_id"\s*:\s*")[^"]+', r'\1[redacted]', value)
    value = re.sub(r"(?i)(request_id:\s*)[0-9a-f-]{20,}", r"\1[redacted]", value)
    return value


def deepseek_peak(at: datetime) -> bool:
    weekday = at.weekday() < 5
    return weekday and ((1 <= at.hour < 4) or (6 <= at.hour < 10))


def normalize_usage(provider: str, payload: dict | None,
                    call_start: datetime | None = None) -> tuple[dict, dict, float, dict]:
    usage = (payload or {}).get("usage") or {}
    rates: dict
    input_tokens = output_tokens = cached_tokens = 0
    normalized: dict[str, Any] = {"raw_fields": sorted(usage.keys()) if isinstance(usage, dict) else []}
    if provider == "openai":
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cached_tokens = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        normalized.update(input_tokens=input_tokens, output_tokens=output_tokens,
                          cached_input_tokens=cached_tokens, reasoning_tokens=reasoning,
                          mapping={"input": "usage.prompt_tokens", "output": "usage.completion_tokens",
                                   "reasoning": "usage.completion_tokens_details.reasoning_tokens",
                                   "cached_input": "usage.prompt_tokens_details.cached_tokens"})
        rates = {"input": PRICES["openai"]["input"], "cached_input": PRICES["openai"]["cached_input"], "output": PRICES["openai"]["output"]}
        source = RATE_SOURCES["openai"]
        tier = None
    elif provider == "deepseek":
        at = call_start or now_utc()
        tier = "peak" if deepseek_peak(at) else "offpeak"
        tier_key = "deepseek_peak" if tier == "peak" else "deepseek_offpeak"
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cached_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        normalized.update(input_tokens=input_tokens, output_tokens=output_tokens,
                          cached_input_tokens=cached_tokens, reasoning_tokens=reasoning,
                          reasoning_content_present=False,
                          mapping={"input": "usage.prompt_tokens", "output": "usage.completion_tokens",
                                   "cached_input": "usage.prompt_cache_hit_tokens",
                                   "reasoning": "usage.completion_tokens_details.reasoning_tokens or absent"})
        rates = {"input": PRICES[tier_key]["input"], "cached_input": PRICES[tier_key]["cached_input"], "output": PRICES[tier_key]["output"]}
        source = RATE_SOURCES["deepseek"]
    elif provider == "gemini":
        meta = (payload or {}).get("usageMetadata") or {}
        input_tokens = int(meta.get("promptTokenCount") or 0)
        output_tokens = int(meta.get("candidatesTokenCount") or 0)
        cached_tokens = int(meta.get("cachedContentTokenCount") or 0)
        normalized = {"input_tokens": input_tokens, "output_tokens": output_tokens,
                      "cached_input_tokens": cached_tokens,
                      "reasoning_tokens": meta.get("thoughtsTokenCount"),
                      "mapping": {"input": "usageMetadata.promptTokenCount",
                                  "output": "usageMetadata.candidatesTokenCount",
                                  "cached_input": "usageMetadata.cachedContentTokenCount"}}
        rates = {"input": PRICES["gemini"]["input"], "cached_input": PRICES["gemini"]["cached_input"], "output": PRICES["gemini"]["output"]}
        source = RATE_SOURCES["gemini"]
        tier = None
    elif provider == "jev":
        use = (payload or {}).get("usage") or {}
        input_tokens = int(use.get("inputTokens") or 0)
        output_tokens = int(use.get("outputTokens") or 0)
        cached_tokens = 0
        normalized = {"input_tokens": input_tokens, "output_tokens": output_tokens,
                      "cached_input_tokens": None, "reasoning_tokens": None,
                      "mapping": {"input": "usage.inputTokens", "output": "usage.outputTokens"},
                      "raw_usage_fields": sorted(use.keys()) if isinstance(use, dict) else []}
        rates = {"input": PRICES["jev"]["input"], "cached_input": PRICES["jev"]["cached_input"], "output": PRICES["jev"]["output"]}
        source = RATE_SOURCES["jev"]
        tier = None
    else:
        raise ValueError(provider)
    amount = ((max(input_tokens - cached_tokens, 0) * rates["input"])
              + cached_tokens * rates["cached_input"]
              + output_tokens * rates["output"]) / 1_000_000
    cost = {"amount": round(amount, 12), "rates_used_usd_per_million": rates,
            "rate_source": source, "tier": tier}
    tokens = {"input": input_tokens, "output": output_tokens, "cached_input": cached_tokens}
    return normalized, cost, amount, tokens


def extract_text(provider: str, payload: dict) -> str:
    if provider in {"openai", "deepseek"}:
        message = ((payload.get("choices") or [{}])[0].get("message") or {})
        content = message.get("content")
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content or "")
    if provider == "gemini":
        candidates = payload.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        return "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
    return json.dumps(payload.get("answers", payload), ensure_ascii=False)


def write_attempt(*, out_dir: str, call_id: str, arm_id: str, provider: str,
                  model_id_sent: str, endpoint: str, settings: dict,
                  status: int | None, latency_ms: int, payload: dict | None,
                  output: str | None = None, error: str | None = None,
                  call_start: datetime | None = None, attempt: int = 1) -> dict:
    normalized, cost, amount, tokens = normalize_usage(provider, payload, call_start) if payload is not None else (
        {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0},
        {"amount": 0.0, "rates_used_usd_per_million": {}, "rate_source": RATE_SOURCES.get(provider), "tier": None},
        0.0,
        {"input": 0, "output": 0, "cached_input": 0},
    )
    if provider == "deepseek" and payload is not None:
        message = ((payload.get("choices") or [{}])[0].get("message") or {})
        normalized["reasoning_content_present"] = message.get("reasoning_content") is not None
    output_text = output if output is not None else (extract_text(provider, payload) if payload is not None else None)
    if output_text is not None:
        output_text = sanitize(output_text)
    artifact: dict[str, Any] = {
        "call_id": call_id,
        "attempt": attempt,
        "arm_id": arm_id,
        "provider": provider,
        "model_id_sent": model_id_sent,
        "endpoint": endpoint,
        "call_start_utc": utc_string(call_start),
        "settings": settings,
        "http_status": status,
        "latency_ms": latency_ms,
        "usage": normalized,
        "cost": cost,
        "output": None,
    }
    if payload is not None:
        if provider in {"openai", "deepseek"} and payload.get("model"):
            artifact["provider_response_model_id"] = payload.get("model")
        if provider == "gemini":
            if payload.get("modelVersion"):
                artifact["provider_response_model_version"] = payload.get("modelVersion")
            if payload.get("model"):
                artifact["provider_response_model_id"] = payload.get("model")
    if output_text is not None:
        encoded = output_text.encode("utf-8")
        if len(encoded) > 100_000:
            artifact["output"] = {
                "head": output_text[:40_000], "tail": output_text[-40_000:],
                "length_chars": len(output_text), "length_bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        else:
            artifact["output"] = output_text
    if error:
        artifact["error"] = sanitize(error)
    stem = f"{call_id}-a{attempt}"
    relative = Path("raw") / "responses" / out_dir / f"{stem}.json"
    collision = 2
    while (ROOT / relative).exists():
        relative = Path("raw") / "responses" / out_dir / f"{stem}-r{collision}.json"
        collision += 1
    artifact["artifact"] = relative.as_posix()
    write_json(ROOT / relative, artifact)
    return {**artifact, "cost_amount": amount, "tokens": tokens, "artifact": relative.as_posix()}


def request_json(*, provider: str, call_id: str, arm_id: str, model_id: str,
                 endpoint: str, settings: dict, method: str = "POST",
                 body: dict | None = None, headers: dict | None = None,
                 timeout: int = 180, out_dir: str, max_retries: int = 2,
                 retry_backoff: float = 2.0) -> tuple[dict | None, list[dict]]:
    history: list[dict] = []
    for attempt in range(1, max_retries + 2):
        started = now_utc()
        tick = time.perf_counter()
        try:
            response = requests.request(method, endpoint, json=body if method != "GET" else None,
                                        headers=headers, timeout=timeout)
            elapsed = int((time.perf_counter() - tick) * 1000)
            try:
                payload = response.json()
            except ValueError:
                payload = None
            output = None if payload is not None else response.text
            result = write_attempt(out_dir=out_dir, call_id=call_id, arm_id=arm_id,
                                   provider=provider, model_id_sent=model_id,
                                   endpoint=endpoint, settings=settings,
                                   status=response.status_code, latency_ms=elapsed,
                                   payload=payload, output=output,
                                   error=(json.dumps(payload.get("error"), ensure_ascii=False)
                                          if not response.ok and isinstance(payload, dict) and payload.get("error")
                                          else (response.text[:1000] if not response.ok and payload is None else None)),
                                   call_start=started,
                                   attempt=attempt)
            history.append(result)
            if response.ok and isinstance(payload, dict):
                return payload, history
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt > max_retries:
                return None, history
        except requests.RequestException as exc:
            elapsed = int((time.perf_counter() - tick) * 1000)
            result = write_attempt(out_dir=out_dir, call_id=call_id, arm_id=arm_id,
                                   provider=provider, model_id_sent=model_id,
                                   endpoint=endpoint, settings=settings, status=None,
                                   latency_ms=elapsed, payload=None,
                                   error=f"{type(exc).__name__}: {exc}",
                                   call_start=started, attempt=attempt)
            history.append(result)
            if attempt > max_retries:
                return None, history
        time.sleep(retry_backoff * attempt)
    return None, history


def gemini_headers() -> dict:
    return {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"}


def chat_headers(provider: str) -> dict:
    name = "OPENAI_API_KEY" if provider == "openai" else "DEEPSEEK_API_KEY"
    return {"Authorization": f"Bearer {os.environ[name]}", "Content-Type": "application/json"}


def jev_headers() -> dict:
    return {
        "authorization": f"Bearer {os.environ['AI_GATEWAY_API_KEY']}",
        "ai-model-id": MODELS["jev"],
        "ai-evaluation-model-specification-version": "4",
        "ai-gateway-protocol-version": "0.0.1",
        "ai-gateway-auth-method": "api-key",
        "content-type": "application/json",
    }


def rolling_totals() -> dict:
    total = 0.0
    calls = 0
    input_tokens = output_tokens = 0
    for path in (RAW / "responses").rglob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        calls += 1
        total += float((row.get("cost") or {}).get("amount") or 0)
        input_tokens += int((row.get("usage") or {}).get("input_tokens") or 0)
        output_tokens += int((row.get("usage") or {}).get("output_tokens") or 0)
    return {"calls": calls, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "estimated_cost_usd": round(total, 12), "hard_cap_usd": 8.0}


def assert_budget(estimate_usd: float = 0.0) -> None:
    total = float(rolling_totals()["estimated_cost_usd"])
    if total + estimate_usd >= 7.50:
        raise RuntimeError(f"budget stop before call: recorded ${total:.6f} + bounded estimate ${estimate_usd:.6f} reaches $7.50 reserve")
