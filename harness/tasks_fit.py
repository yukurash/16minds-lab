"""実験1：適性表の 8 タスク。

題材は yukurash.github.io の index.html（単一ファイル 799 行、CSS 275 行 + セレクト
画面の JS 込み）。実在のコードをそのまま使い、レビュー能力を測るための欠陥を 4 件だけ
仕込んである（内容は fixtures/ANSWERS.md、実験完了まで封印）。

8 タスクすべてが同じ 1 ファイルで成立するように書いてある。出力スキーマは全タスク共通に
して、タイプ間・タスク間でそのまま比べられるようにした。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "index.html"

# 全タスク共通。指摘は最大 5 件。
SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "指摘の見出し（40字以内）"},
                    "why": {"type": "string", "description": "なぜ問題か / なぜそう判断したか（120字以内）"},
                    "where": {"type": "string", "description": "該当箇所。行番号・セレクタ名・関数名など。該当なしなら '-'"},
                },
                "required": ["title", "why", "where"],
                "additionalProperties": False,
            },
        },
        "top_recommendation": {"type": "string", "description": "最優先で着手すべき一手（80字以内）"},
        "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
    },
    "required": ["findings", "top_recommendation", "confidence"],
    "additionalProperties": False,
}

_COMMON = """あなたはこの HTML ファイル 1 枚でできた個人ポートフォリオサイトのレビューを頼まれた。
サイトは https://yukurash.github.io/ で公開されている。12 個の制作物カードを並べ、
カードを選ぶと右のパネルに詳細が出る「セレクト画面」型の UI になっている。

指摘は最大 5 件。多く挙げることより、あなたが本当に重要だと思う順に並べることを優先しろ。
where には行番号・セレクタ名・関数名など、実際に手を動かせる位置情報を書け。
"""

TASKS = {
    "bug": {
        "title": "バグ調査",
        "instruction": """このコードには実際に動作を壊している不具合が含まれている。
挙動として何が起きるかを推理し、原因のコードを特定しろ。

「〜かもしれない」で終わる推測ではなく、どの行がどう間違っていて画面上で何が起きるかを書け。
スタイルの好みや設計の善し悪しは対象外。動作が壊れているものだけを挙げろ。""",
    },
    "spec_hole": {
        "title": "仕様の穴探し",
        "instruction": """このサイトに「実装されていないが、あるべきもの」を挙げろ。
書かれているコードの不具合ではなく、書かれていないことが問題になっているものを探せ。

アクセシビリティ、キーボード操作、支援技術への通知、SNS 共有時の見え方、検索エンジン、
多言語、公開後の運用——どの切り口から入るかはあなたに任せる。""",
    },
    "design_review": {
        "title": "設計レビュー",
        "instruction": """このサイトは HTML・CSS・JavaScript を 1 ファイル 799 行に詰め込んでいる。
ビルドツールもフレームワークも使っていない。

この構成そのものを評価しろ。何を得ていて、何を失っているか。
このまま続けたとき最初に壊れるのはどこか。""",
    },
    "naming": {
        "title": "命名",
        "instruction": """CSS のクラス名と DOM の id を評価し、改名案を出せ。

現状は sect / sect-h / sect-t / kick / slab / cell / em / nm / ja / mk / id / doc / cd /
panel / pid / st / go / art / artt / lb / tt / ldbar / fx / cut / keys / reads / glabel
のような短縮名で、id は p-id / p-nm / p-ch / p-ja / p-into / p-tech / p-desc / p-go /
p-host / p-art / p-artt という接頭辞方式になっている。

半年後の自分が読めるか、という基準で判断しろ。""",
    },
    "estimate": {
        "title": "見積もり",
        "instruction": """次の変更をこのコードベースに入れる。工数を見積もり、作業を分解しろ。

  作品カードを 12 件から 30 件に増やし、
  「Claude Code / Azure / iOS / Web」のタグで絞り込めるようにする。

見積もりの単位は人日でも時間でもよいが、根拠になる数字を必ず示せ。
現在の実装のどこが効いて重くなる（あるいは軽く済む）のかを具体的に書け。""",
    },
    "incident": {
        "title": "障害対応",
        "instruction": """本番で次の報告が来た。あなたが一次対応者だ。

  「GitHub Pages に push したあと、スマホで開いたら真っ白になった。
   PC では見えている。あと X に貼ってもサムネイルもタイトルも出ない。」

このコードを見て、切り分けの手順と、疑うべき箇所を優先度順に挙げろ。
報告のうち再現しそうにないものがあれば、それも指摘しろ。""",
    },
    "refactor": {
        "title": "リファクタ判断",
        "instruction": """このファイルをどうするか決めろ。選択肢は例えば次のようなものだ。

  a. 1 ファイルのまま維持する
  b. CSS と JS を別ファイルに切り出す
  c. 12 件の作品データを JSON に外出しし、カードを生成する

どれを選ぶか、あるいは選ばないかを決め、その判断が覆る条件も書け。
「場合による」で終わらせるな。""",
    },
    "tech_choice": {
        "title": "技術選定",
        "instruction": """このサイトを素の HTML のまま続けるか、静的サイトジェネレータ
（Astro / Eleventy / Hugo など）に載せ替えるかを決めろ。

更新頻度は月に 1〜2 回、作品を 1 件足すか文言を直す程度。書いているのは本人 1 人。
公開先は GitHub Pages。

移行する場合はどれを選ぶかまで決めろ。しない場合は、何が起きたら考え直すかを書け。""",
    },
}

ORDER = list(TASKS.keys())


def material() -> str:
    src = FIXTURE.read_text(encoding="utf-8")
    lines = src.splitlines()
    numbered = "\n".join(f"{i + 1:4d}| {ln}" for i, ln in enumerate(lines))
    return numbered


def prompt(task_id: str) -> str:
    t = TASKS[task_id]
    return (
        _COMMON
        + "\n## 依頼\n\n"
        + t["instruction"].strip()
        + "\n\n## index.html（行番号つき）\n\n```\n"
        + material()
        + "\n```\n"
    )


if __name__ == "__main__":
    for k in ORDER:
        print(f"{k:14s} {TASKS[k]['title']:10s} {len(prompt(k)):7d} chars")
