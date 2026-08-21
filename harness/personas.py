"""agents/<type>.md を system prompt に変換する。

16minds-plugin の人格定義をそのまま使う。ただし2箇所だけ落とす:

1. YAML frontmatter（name / description）
   → Claude Code のサブエージェント登録用メタデータであり、人格の記述ではない。
2. 末尾の「出力フォーマットは呼び出し元のコマンドが指定する。…」の節
   → /mind 用のフォーマット指示。この実験では --json-schema で上書きするので外す。

それ以外は一切書き換えない。この前処理は RULES.md に明記してある。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT / ".plugin-src" / "agents"

TYPES = [
    "intj", "intp", "entj", "entp",
    "infj", "infp", "enfj", "enfp",
    "istj", "isfj", "estj", "esfj",
    "istp", "isfp", "estp", "esfp",
]

_TAIL = "出力フォーマットは呼び出し元のコマンドが指定する"


def load(t: str) -> str:
    raw = (AGENT_DIR / f"{t}.md").read_text(encoding="utf-8")

    # 1. frontmatter を落とす
    body = re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "", raw, flags=re.S)

    # 2. 末尾のフォーマット指示節を落とす（直前の水平線ごと）
    i = body.find(_TAIL)
    if i != -1:
        body = body[:i]
        body = re.sub(r"(?:\r?\n)*-{3,}\s*\Z", "", body)

    return body.strip() + "\n"


def all_personas() -> dict[str, str]:
    return {t: load(t) for t in TYPES}


if __name__ == "__main__":
    for t in TYPES:
        s = load(t)
        assert "name:" not in s.split("\n")[0], t
        assert _TAIL not in s, t
        print(f"{t}: {len(s):5d} chars, starts: {s.splitlines()[0][:40]}")
