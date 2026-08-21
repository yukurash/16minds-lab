"""claude -p をクリーンルームで叩くための最小ラッパ。

- 既定のシステムプロンプトは --system-prompt で置き換える（Claude Code の足場を混入させない）
- --safe-mode で CLAUDE.md / skills / plugins / hooks / MCP を全部無効化する
  （--bare は API キー必須になるので使わない。サブスク認証のまま走らせたい）
- --tools "" でツール使用を封じ、純粋な文章生成にする
- --json-schema で出力形式を強制する
- お題本文は 47KB あり Windows のコマンドライン長を超えるので stdin から渡す

結果は results/raw/<key>.json に置き、同じキーは再実行しない（レジューム可能）。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"

CLAUDE_BIN = os.environ.get(
    "CLAUDE_BIN", str(Path.home() / ".local" / "bin" / "claude.exe")
)

# 1 リクエストあたりの上限。これを超えたら異常とみなして落とす。
TIMEOUT_SEC = int(os.environ.get("CELL_TIMEOUT", "300"))


class CallError(RuntimeError):
    pass


def cache_key(*parts: str) -> str:
    h = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return h


def call(
    system: str,
    prompt: str,
    schema: dict | None = None,
    model: str = "sonnet",
    tag: str = "",
    key: str | None = None,
    retries: int = 3,
) -> dict:
    """1 セル分の実行。返り値は {'data': <schema 通りの dict もしくは text>, 'meta': {...}}。"""
    RAW.mkdir(parents=True, exist_ok=True)
    k = key or cache_key(model, system, prompt, json.dumps(schema or {}, sort_keys=True))
    path = RAW / f"{k}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    cmd = [
        CLAUDE_BIN,
        "-p",
        "--system-prompt",
        system,
        "--model",
        model,
        "--tools",
        "",
        "--safe-mode",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format",
        "json",
    ]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema, ensure_ascii=False)]

    last = ""
    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            last = f"timeout after {TIMEOUT_SEC}s"
            time.sleep(3 * attempt)
            continue

        try:
            env = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last = f"unparsable stdout: {proc.stdout[:300]} / stderr: {proc.stderr[:300]}"
            time.sleep(3 * attempt)
            continue

        if env.get("is_error"):
            last = str(env.get("result"))[:300]
            time.sleep(3 * attempt)
            continue

        payload = env.get("result")
        if schema is not None and isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                last = f"result was not JSON: {str(payload)[:300]}"
                time.sleep(3 * attempt)
                continue

        rec = {
            "key": k,
            "tag": tag,
            "model": model,
            "data": payload,
            "meta": {
                "attempt": attempt,
                "usage": env.get("usage"),
                "cost_usd": env.get("total_cost_usd"),
                "duration_ms": env.get("duration_ms"),
                "session_id": env.get("session_id"),
            },
        }
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return rec

    raise CallError(f"[{tag}] failed after {retries} attempts: {last}")


def total_cost() -> float:
    s = 0.0
    for p in RAW.glob("*.json"):
        try:
            s += json.loads(p.read_text(encoding="utf-8"))["meta"].get("cost_usd") or 0.0
        except Exception:
            pass
    return s
