"""Chat-model clients with retry, failover and a circuit breaker (D-011, D-013, D-014, D-017).

    text, provider = chat(system, messages, json_mode=True)

Order: Ollama cloud (gpt-oss:120b), then each Gemini model in config.GEMINI_MODELS. A timeout or
5xx is retried once; a 429 (rate limit) or 503 moves straight on to the next provider. A
provider that fails CIRCUIT_FAILURES times in a row is skipped for CIRCUIT_COOLDOWN seconds.
If every provider fails, LLMError is raised with kind "rate_limit" or "unavailable" so the API
can show a friendly message. Only `content` is ever returned: Ollama's `thinking` field is dropped.
"""
import os
import threading
import time

import httpx

from backend import config

try:
    from dotenv import load_dotenv
    load_dotenv(config.ROOT / ".env")
except ImportError:
    pass


class LLMError(Exception):
    def __init__(self, kind, detail=""):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind            # rate_limit | unavailable | bad_output | no_key


_client = httpx.Client(timeout=httpx.Timeout(config.TIMEOUT_READ, connect=config.TIMEOUT_CONNECT))
_lock = threading.Lock()
STATUS = {}     # provider name -> {"ok": bool, "last": ts, "error": str, "failures": n, "skip_until": ts}


def _record(name, ok, error=""):
    with _lock:
        s = STATUS.setdefault(name, {"failures": 0, "skip_until": 0})
        s.update(ok=ok, last=time.time(), error=error[:120])
        s["failures"] = 0 if ok else s["failures"] + 1
        if s["failures"] >= config.CIRCUIT_FAILURES:
            s["skip_until"] = time.time() + config.CIRCUIT_COOLDOWN


def _skipped(name):
    return STATUS.get(name, {}).get("skip_until", 0) > time.time()


class _HTTPFail(Exception):
    def __init__(self, status, text=""):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.text = text


def _ollama(system, messages, json_mode):
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        raise LLMError("no_key", "OLLAMA_API_KEY not set")
    body = {"model": config.OLLAMA_MODEL, "stream": False,
            "messages": [{"role": "system", "content": system}] + messages,
            "options": {"temperature": config.TEMPERATURE}, "think": config.OLLAMA_THINK}
    if json_mode:
        body["format"] = "json"
    r = _client.post(config.OLLAMA_URL, json=body, headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        raise _HTTPFail(r.status_code, r.text[:200])
    data = r.json()
    usage = {"in": data.get("prompt_eval_count", 0), "out": data.get("eval_count", 0)}
    return (data.get("message") or {}).get("content", ""), usage


def _gemini(model, system, messages, json_mode):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("no_key", "GEMINI_API_KEY not set")
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages]
    gen = {"temperature": config.TEMPERATURE}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen}
    r = _client.post(config.GEMINI_URL.format(model=model), json=body, headers={"x-goog-api-key": key})
    if r.status_code != 200:
        raise _HTTPFail(r.status_code, r.text[:200])
    data = r.json()
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    meta = data.get("usageMetadata", {})
    return text, {"in": meta.get("promptTokenCount", 0), "out": meta.get("candidatesTokenCount", 0)}


def _providers():
    for name in config.PROVIDER_ORDER:
        if name == "ollama":
            yield "ollama", lambda s, m, j: _ollama(s, m, j)
        elif name == "gemini":
            for model in config.GEMINI_MODELS:
                yield f"gemini:{model}", (lambda mdl: lambda s, m, j: _gemini(mdl, s, m, j))(model)


def chat(system: str, messages: list, json_mode=False):
    """Return (text, provider_name, usage). Raises LLMError when every provider fails."""
    saw_429 = False
    errors = []
    for name, call in _providers():
        if _skipped(name):
            errors.append(f"{name}: circuit open")
            continue
        for attempt in range(config.RETRIES + 1):
            try:
                text, usage = call(system, messages, json_mode)
                if not text.strip():
                    raise _HTTPFail(200, "empty content")
                _record(name, True)
                return text, name, usage
            except LLMError as e:          # missing key: skip this provider
                errors.append(f"{name}: {e.kind}")
                _record(name, False, e.kind)
                break
            except _HTTPFail as e:
                _record(name, False, f"HTTP {e.status}")
                errors.append(f"{name}: HTTP {e.status}")
                if e.status == 429:
                    saw_429 = True
                if e.status in (429, 503, 400, 401, 403, 404):
                    break                  # no point retrying: go to the next provider
            except (httpx.TimeoutException, httpx.TransportError) as e:
                _record(name, False, type(e).__name__)
                errors.append(f"{name}: {type(e).__name__}")
            if attempt < config.RETRIES:
                time.sleep(0.8)
    raise LLMError("rate_limit" if saw_429 else "unavailable", "; ".join(errors))


def provider_status():
    now = time.time()
    return {name: {"ok": s.get("ok"), "last_error": s.get("error") or None,
                   "seconds_since_last_call": round(now - s["last"]) if s.get("last") else None,
                   "circuit_open": s.get("skip_until", 0) > now}
            for name, s in STATUS.items()}
