"""採点。

適性（fit）:
  タスク × 反復ごとに、16タイプの出力を匿名化・順序シャッフルして judge に一括で渡す。
  judge はどのラベルがどのタイプかを知らない。
    - 検出率 : ANSWERS.md の正解 ID をいくつ当てたか（bug / spec_hole / incident のみ）。主指標
    - 有用性 : 0-3
    - 具体性 : 0-3
    - 独自性 : その16件の中で他の誰も挙げていない論点の数

相性（pair）:
  主指標は「新規論点の創出数」。両者の立論のどちらにも無かった論点が、反論・再反論を
  通していくつ生まれたか。副指標として論点接触率と、Phase 3 の修正宣言を使う。

  python harness/judge.py fit --slot main --repeats 3
  python harness/judge.py pair --topic portfolio_failures
"""

from __future__ import annotations

import argparse
import json
import random
import re
import string
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claudecall as cc

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
ANSWERS_MD = ROOT / "fixtures" / "ANSWERS.md"

# judge は型名を知らない。人格も持たせない。
JUDGE_SYSTEM = """あなたはソフトウェアレビューの採点者だ。

複数の匿名レビュアーが同じ課題に出した指摘を受け取り、指示された基準で採点する。
書き手が誰かは分からないし、推測もしない。文体の巧拙ではなく中身だけを見る。
甘くつけない。根拠のない一般論は評価しない。
"""

FIT_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "matched": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "当てた正解 ID の配列。無ければ空配列",
                    },
                    "usefulness": {"type": "integer", "minimum": 0, "maximum": 3},
                    "specificity": {"type": "integer", "minimum": 0, "maximum": 3},
                    "unique_points": {"type": "integer", "minimum": 0},
                    "note": {"type": "string", "description": "採点理由を一行で"},
                },
                "required": ["label", "matched", "usefulness", "specificity", "unique_points", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

PAIR_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "new_points": {"type": "integer", "minimum": 0, "description": "両者の立論のどちらにも無かった論点が、反論・再反論で新しくいくつ生まれたか"},
        "new_point_list": {"type": "array", "items": {"type": "string"}},
        "contact_a": {"type": "integer", "minimum": 0, "maximum": 3, "description": "A の反論が B の実際の主張に触れていた度合い"},
        "contact_b": {"type": "integer", "minimum": 0, "maximum": 3},
        "parallel": {"type": "boolean", "description": "最後まで評価軸が一度も交差せず平行線だったか"},
        "note": {"type": "string"},
    },
    "required": ["new_points", "new_point_list", "contact_a", "contact_b", "parallel", "note"],
    "additionalProperties": False,
}


def load_answers() -> dict:
    md = ANSWERS_MD.read_text(encoding="utf-8")
    m = re.search(r"```json\s*(\{.*?\})\s*```", md, flags=re.S)
    if not m:
        raise RuntimeError("ANSWERS.md に json ブロックが無い")
    data = json.loads(m.group(1))
    by_task: dict[str, list[dict]] = defaultdict(list)
    for a in data["answers"]:
        by_task[a["task"]].append(a)
    return by_task


LABELS = list(string.ascii_uppercase[:16])


def judge_fit(slot: str, model: str) -> None:
    rows = json.loads((RESULTS / "fit.json").read_text(encoding="utf-8"))["rows"]
    rows = [r for r in rows if r["slot"] == slot]
    by_cell: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        by_cell[(r["task"], r["rep"])].append(r)

    answers = load_answers()
    out = []

    for (task, rep), group in sorted(by_cell.items()):
        # ラベル割り当てはタスクと反復で決まる固定シードでシャッフルする（再現可能）
        rnd = random.Random(f"{slot}/{task}/{rep}")
        group = sorted(group, key=lambda r: r["type"])
        order = list(range(len(group)))
        rnd.shuffle(order)
        mapping = {LABELS[i]: group[j]["type"] for i, j in enumerate(order)}

        blocks = []
        for i, j in enumerate(order):
            d = group[j]["data"]
            fs = "\n".join(
                f"  - {f['title']} / {f['why']} / 位置: {f['where']}" for f in d["findings"]
            )
            blocks.append(
                f"### レビュアー {LABELS[i]}\n{fs}\n  最優先の一手: {d['top_recommendation']}\n"
            )

        ans = answers.get(task, [])
        if ans:
            ans_txt = "\n".join(
                f"- {a['id']}: {a['title']} — {a['detail']}" for a in ans
            )
            ans_sec = f"""
## 正解リスト

このタスクには、あらかじめ用意した正解がある。各レビュアーがどれを当てたかを判定しろ。

{ans_txt}

判定は厳しくつけろ。同じ現象を指しているときだけ当たりとする。
関連する一般論に触れただけ（「アクセシビリティを見直すべき」など）は当たりにしない。
"""
        else:
            ans_sec = "\n## 正解リスト\n\nこのタスクに正解リストは無い。matched は全員空配列にしろ。\n"

        prompt = f"""{len(group)}人の匿名レビュアーが、同一の HTML ファイルに対する
同一の課題「{task}」に出した指摘だ。
{ans_sec}
## 採点基準

- usefulness 0-3: そのまま着手できる指摘か。0 = 何も言っていない、3 = 明日そのまま直せる
- specificity 0-3: 行番号・セレクタ名・関数名など、位置が特定できているか
- unique_points: この{len(group)}人の中で、そのレビュアーしか挙げていない論点の数

## レビュアーの出力

{chr(10).join(blocks)}
"""
        rec = cc.call(
            system=JUDGE_SYSTEM,
            prompt=prompt,
            schema=FIT_JUDGE_SCHEMA,
            model=model,
            tag=f"judge/fit/{slot}/{task}/rep{rep}",
            key=cc.cache_key("judge", "fit", model, slot, task, str(rep)),
        )
        for it in rec["data"]["items"]:
            t = mapping.get(it["label"])
            if not t:
                continue
            out.append(
                {
                    "slot": slot, "task": task, "rep": rep, "type": t,
                    "matched": it["matched"], "usefulness": it["usefulness"],
                    "specificity": it["specificity"], "unique_points": it["unique_points"],
                    "note": it["note"],
                }
            )
        print(f"  judged {task}/rep{rep}")

    p = RESULTS / f"fit_scores_{slot}.json"
    p.write_text(json.dumps({"scores": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {p}  ({len(out)} scores)")


def judge_pair(topic: str, model: str) -> None:
    rows = json.loads((RESULTS / "pair.json").read_text(encoding="utf-8"))["rows"]
    rows = [r for r in rows if r["topic"] == topic]
    out = []

    for r in rows:
        a, b = r["a"], r["b"]
        prompt = f"""2人の匿名討論者 A と B のディベート記録だ。お題は次のもの。

  {r['topic']}

## 立論

A: {r['brief'][a]['stance']} / {r['brief'][a]['reasoning']}
B: {r['brief'][b]['stance']} / {r['brief'][b]['reasoning']}

## 反論

A → B（突いた点: {r['rebuttal'][a]['target']}）
{r['rebuttal'][a]['rebuttal']}

B → A（突いた点: {r['rebuttal'][b]['target']}）
{r['rebuttal'][b]['rebuttal']}

## 再反論

A（{r['final'][a]['revision']}）: {r['final'][a]['statement']}
B（{r['final'][b]['revision']}）: {r['final'][b]['statement']}

## 採点

- new_points: 立論の段階では A にも B にも出ていなかった論点が、反論・再反論を通して
  いくつ新しく出てきたか。言い換えや強調は数えない。新しい評価軸・新しい事実・新しい
  条件だけを数え、new_point_list に一言ずつ書け。
- contact_a / contact_b: その人の反論が、相手が実際に言ったことに触れていたか。
  0 = 相手の主張と無関係に自説を続けた、3 = 相手の中心的な主張に正面から当たった
- parallel: 最後まで互いの評価軸が一度も交差せず、噛み合わないまま終わったか
"""
        rec = cc.call(
            system=JUDGE_SYSTEM,
            prompt=prompt,
            schema=PAIR_JUDGE_SCHEMA,
            model=model,
            tag=f"judge/pair/{topic}/{r['side']}/{a}-{b}",
            key=cc.cache_key("judge", "pair", model, topic, r["side"], a, b),
        )
        d = rec["data"]
        out.append(
            {
                "topic": topic, "side": r["side"], "a": a, "b": b,
                "new_points": d["new_points"], "new_point_list": d["new_point_list"],
                "contact_a": d["contact_a"], "contact_b": d["contact_b"],
                "parallel": d["parallel"],
                "revision_a": r["final"][a]["revision"],
                "revision_b": r["final"][b]["revision"],
                "note": d["note"],
            }
        )
        print(f"  judged {a} vs {b}: new={d['new_points']} parallel={d['parallel']}")

    p = RESULTS / f"pair_scores_{topic}.json"
    p.write_text(json.dumps({"scores": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {p}  ({len(out)} scores)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["fit", "pair"])
    ap.add_argument("--slot", default="main")
    ap.add_argument("--topic", default="portfolio_failures")
    ap.add_argument("--model", default="opus", help="採点は本数が少ないので既定は opus")
    a = ap.parse_args()
    if a.mode == "fit":
        judge_fit(a.slot, a.model)
    else:
        judge_pair(a.topic, a.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
