"""ヒートマップ 2 枚。

  適性表: 16 タイプ × 8 タスク
  相性表: 16 × 16（対称）

ラベルはすべて ASCII にしてある（日本語フォントの有無に結果が左右されないようにするため）。
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import personas  # noqa: E402
import tasks_fit as TF  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIG = RESULTS / "figures"

TYPES = personas.TYPES
OBJECTIVE = {"bug", "spec_hole", "incident"}


def _answer_counts() -> dict[str, int]:
    import judge
    by_task = judge.load_answers()
    return {k: len(v) for k, v in by_task.items()}


def fit_matrix(slot: str = "main") -> tuple[np.ndarray, list[str]]:
    """セルの値 = 検出率(0-1) があるタスクはそれ、無いタスクは (有用性+具体性)/6。"""
    p = RESULTS / f"fit_scores_{slot}.json"
    scores = json.loads(p.read_text(encoding="utf-8"))["scores"]
    n_ans = _answer_counts()

    acc: dict[tuple[str, str], list[float]] = defaultdict(list)
    for s in scores:
        if s["task"] in OBJECTIVE:
            v = len(set(s["matched"])) / max(1, n_ans.get(s["task"], 1))
        else:
            v = (s["usefulness"] + s["specificity"]) / 6.0
        acc[(s["type"], s["task"])].append(v)

    tasks = TF.ORDER
    m = np.full((len(TYPES), len(tasks)), np.nan)
    for i, t in enumerate(TYPES):
        for j, task in enumerate(tasks):
            vs = acc.get((t, task))
            if vs:
                m[i, j] = sum(vs) / len(vs)
    return m, tasks


def pair_matrix(topic: str = "portfolio_failures", side: str = "fwd") -> np.ndarray:
    p = RESULTS / f"pair_scores_{topic}.json"
    scores = [s for s in json.loads(p.read_text(encoding="utf-8"))["scores"] if s["side"] == side]
    idx = {t: i for i, t in enumerate(TYPES)}
    m = np.full((16, 16), np.nan)
    for s in scores:
        i, j = idx[s["a"]], idx[s["b"]]
        m[i, j] = m[j, i] = s["new_points"]
    return m


def _heat(m, xlabels, ylabels, title, cbar, path, fmt="{:.2f}"):
    fig, ax = plt.subplots(figsize=(max(7, len(xlabels) * 0.62), len(ylabels) * 0.46 + 2.2))
    im = ax.imshow(np.ma.masked_invalid(m), cmap="magma", aspect="auto")
    ax.set_xticks(range(len(xlabels)), xlabels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(ylabels)), ylabels, fontsize=9)
    ax.set_title(title, fontsize=12, pad=12)
    fig.colorbar(im, ax=ax, label=cbar, shrink=0.82)

    finite = m[np.isfinite(m)]
    mid = (finite.max() + finite.min()) / 2 if finite.size else 0
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if np.isfinite(m[i, j]):
                ax.text(j, i, fmt.format(m[i, j]), ha="center", va="center", fontsize=7,
                        color="white" if m[i, j] < mid else "black")
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    print(f"wrote {path}")


def main() -> None:
    if (RESULTS / "fit_scores_main.json").exists():
        m, tasks = fit_matrix("main")
        _heat(m, tasks, TYPES,
              "16-minds fitness: type x task (higher is better)",
              "score (0-1)", FIG / "fitness.png")

    for topic in ("portfolio_failures", "article_axis"):
        if (RESULTS / f"pair_scores_{topic}.json").exists():
            m = pair_matrix(topic)
            _heat(m, TYPES, TYPES,
                  f"16-minds chemistry: new points per debate ({topic})",
                  "new points", FIG / f"chemistry_{topic}.png", fmt="{:.0f}")


if __name__ == "__main__":
    main()
