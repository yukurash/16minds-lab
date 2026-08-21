"""実験2のランナー：立論16 → 反論240 → 再反論240。

  python harness/run_pair.py --topic portfolio_failures --pairs pilot
  python harness/run_pair.py --topic portfolio_failures --pairs all
  python harness/run_pair.py --topic article_axis --pairs sample20
  python harness/run_pair.py --topic portfolio_failures --pairs order10 --reverse

立論は「相手に依存しない」ので 16 タイプぶん 1 回だけ作り、全ペアで使い回す。
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claudecall as cc
import personas
import tasks_pair as TP

OUT = Path(__file__).resolve().parent.parent / "results" / "pair.json"

# パイロット：NT / NF / SJ / SP から 1 タイプずつ
PILOT = ["intj", "enfp", "istj", "esfp"]
# 別お題での追試に使う代表ペア（群内・群間がまんべんなく入るように選ぶ）
SAMPLE20_TYPES = ["intj", "entp", "infj", "enfp", "istj", "esfj", "istp", "estp"]


def pair_list(kind: str) -> list[tuple[str, str]]:
    if kind == "pilot":
        return list(itertools.combinations(PILOT, 2))
    if kind == "sample20":
        return list(itertools.combinations(SAMPLE20_TYPES, 2))[:20]
    if kind == "order10":
        return list(itertools.combinations(personas.TYPES, 2))[:10]
    return list(itertools.combinations(personas.TYPES, 2))


def brief(t: str, topic: str, model: str) -> dict:
    return cc.call(
        system=personas.load(t),
        prompt=TP.brief_prompt(topic),
        schema=TP.BRIEF_SCHEMA,
        model=model,
        tag=f"pair/{topic}/brief/{t}",
        key=cc.cache_key("pair", "brief", model, topic, t),
    )["data"]


def one_pair(a: str, b: str, topic: str, model: str, briefs: dict, reverse: bool) -> dict:
    """a が先攻。reverse のときは呼び出し側で (b, a) を渡す。"""
    ba, bb = briefs[a], briefs[b]
    side = "rev" if reverse else "fwd"

    def reb(me: str, own: dict, opp: dict) -> dict:
        return cc.call(
            system=personas.load(me),
            prompt=TP.rebuttal_prompt(topic, own, opp),
            schema=TP.REBUTTAL_SCHEMA,
            model=model,
            tag=f"pair/{topic}/{side}/{a}-{b}/reb/{me}",
            key=cc.cache_key("pair", "reb", model, topic, side, a, b, me),
        )["data"]

    ra = reb(a, ba, bb)
    rb = reb(b, bb, ba)

    def fin(me: str, own: dict, own_reb: dict, opp_reb: dict) -> dict:
        return cc.call(
            system=personas.load(me),
            prompt=TP.final_prompt(topic, own, own_reb, opp_reb),
            schema=TP.FINAL_SCHEMA,
            model=model,
            tag=f"pair/{topic}/{side}/{a}-{b}/fin/{me}",
            key=cc.cache_key("pair", "fin", model, topic, side, a, b, me),
        )["data"]

    fa = fin(a, ba, ra, rb)
    fb = fin(b, bb, rb, ra)

    return {
        "topic": topic,
        "side": side,
        "a": a,
        "b": b,
        "model": model,
        "brief": {a: ba, b: bb},
        "rebuttal": {a: ra, b: rb},
        "final": {a: fa, b: fb},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="portfolio_failures", choices=list(TP.TOPICS))
    ap.add_argument("--pairs", default="pilot", choices=["pilot", "all", "sample20", "order10"])
    ap.add_argument("--reverse", action="store_true", help="先攻後攻を入れ替えて回す（順序効果の確認）")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    pairs = pair_list(a.pairs)
    if a.reverse:
        pairs = [(y, x) for x, y in pairs]
    need = sorted({t for p in pairs for t in p})

    print(f"topic={a.topic} pairs={len(pairs)} types={len(need)} reverse={a.reverse}")
    t0 = time.time()

    print("phase 1: briefs (相手に依存しないので1タイプ1回だけ)")
    briefs: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(brief, t, a.topic, a.model): t for t in need}
        for f in as_completed(futs):
            t = futs[f]
            briefs[t] = f.result()
            print(f"  brief {t}: {briefs[t]['stance'][:40]}")

    print("phase 2-3: rebuttal + final")
    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {
            ex.submit(one_pair, x, y, a.topic, a.model, briefs, a.reverse): (x, y)
            for x, y in pairs
        }
        done = 0
        for f in as_completed(futs):
            x, y = futs[f]
            done += 1
            try:
                rows.append(f.result())
                print(f"  [{done}/{len(pairs)}] {x} vs {y}")
            except Exception as e:  # noqa: BLE001
                errors.append({"a": x, "b": y, "error": str(e)})
                print(f"  [{done}/{len(pairs)}] !! {x} vs {y}: {e}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"rows": [], "errors": []}
    seen = {(r["topic"], r["side"], r["a"], r["b"]) for r in rows}
    merged = rows + [
        r for r in prev.get("rows", []) if (r["topic"], r["side"], r["a"], r["b"]) not in seen
    ]
    OUT.write_text(
        json.dumps({"rows": merged, "errors": errors}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"\ndone in {time.time() - t0:.0f}s  ok={len(rows)} err={len(errors)}")
    print(f"cumulative cost so far: ${cc.total_cost():.2f}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
