"""実験1のランナー：16タイプ × 8タスク × N反復。

  python harness/run_fit.py --repeats 3
  python harness/run_fit.py --repeats 1 --tasks bug,spec_hole --types intj,enfp
  python harness/run_fit.py --repeats 1 --tasks spec_hole --model opus --slot opus

同じセルは results/raw/ にキャッシュされ、再実行しても呼び直さない（レジューム可能）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claudecall as cc
import personas
import tasks_fit as TF

OUT = Path(__file__).resolve().parent.parent / "results" / "fit.json"


def cell(t: str, task: str, rep: int, model: str, slot: str) -> dict:
    system = personas.load(t)
    prompt = TF.prompt(task)
    key = cc.cache_key("fit", slot, model, t, task, f"rep{rep}")
    rec = cc.call(
        system=system,
        prompt=prompt,
        schema=TF.SCHEMA,
        model=model,
        tag=f"fit/{slot}/{task}/{t}/rep{rep}",
        key=key,
    )
    return {
        "slot": slot,
        "task": task,
        "type": t,
        "rep": rep,
        "model": model,
        "key": key,
        "data": rec["data"],
        "cost_usd": rec["meta"].get("cost_usd"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--slot", default="main", help="結果セット名。opus 抜き取りは別スロットにする")
    ap.add_argument("--tasks", default=",".join(TF.ORDER))
    ap.add_argument("--types", default=",".join(personas.TYPES))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    tasks = [x for x in a.tasks.split(",") if x]
    types = [x for x in a.types.split(",") if x]
    jobs = [(t, task, r) for task in tasks for t in types for r in range(a.repeats)]

    print(f"cells: {len(jobs)}  model={a.model}  slot={a.slot}  workers={a.workers}")
    t0 = time.time()
    rows, errors = [], []

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(cell, t, task, r, a.model, a.slot): (t, task, r) for t, task, r in jobs}
        done = 0
        for f in as_completed(futs):
            t, task, r = futs[f]
            done += 1
            try:
                rows.append(f.result())
                print(f"  [{done}/{len(jobs)}] {task}/{t}/rep{r}")
            except Exception as e:  # noqa: BLE001
                errors.append({"type": t, "task": task, "rep": r, "error": str(e)})
                print(f"  [{done}/{len(jobs)}] !! {task}/{t}/rep{r}: {e}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"rows": [], "errors": []}
    seen = {r["key"] for r in rows}
    merged = rows + [r for r in prev.get("rows", []) if r["key"] not in seen]
    OUT.write_text(
        json.dumps({"rows": merged, "errors": errors}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"\ndone in {time.time() - t0:.0f}s  ok={len(rows)} err={len(errors)}")
    print(f"cumulative cost so far: ${cc.total_cost():.2f}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
