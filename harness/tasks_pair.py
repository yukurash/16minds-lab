"""実験2：相性表のペア戦。

16minds-plugin の /pair heavy と同じ 3 フェーズ構成（立論 → 反論 → 再反論）をなぞる。
Phase 3 冒頭で「修正なし / 部分修正」を宣言させるのは既存コマンドの仕様で、これをその
まま「立場修正が起きたか」の指標として使う。

呼び出し回数の最適化:
  Phase 1 の立論は相手に依存せず、お題だけに依存する。だから 16 タイプぶん 1 回だけ
  生成して 120 ペアすべてで使い回す。変数統制としても正しい（同じ立論を、ぶつける相手
  だけ変える）。これで 240 コールぶん減る。
"""

from __future__ import annotations

TOPICS = {
    # 全数（120ペア）を回すお題
    "portfolio_failures": (
        "個人のポートフォリオサイトに、うまくいかなかった制作物やボツにした企画も"
        "載せるべきか。それとも公開するのは完成して動いているものだけにすべきか。"
    ),
    # 相性表がお題に依存しないかを代表ペアで追試するためのお題
    "article_axis": (
        "個人の技術記事は「作った物の紹介」と「検証して数字を出すこと」の"
        "どちらを軸にすべきか。"
    ),
}

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "stance": {"type": "string", "description": "立場を一行で宣言する（40字以内）"},
        "reasoning": {"type": "string", "description": "自分の価値観からその立場に至る筋道。2〜3文、150字程度"},
    },
    "required": ["stance", "reasoning"],
    "additionalProperties": False,
}

REBUTTAL_SCHEMA = {
    "type": "object",
    "properties": {
        "target": {"type": "string", "description": "相手の主張のうち最も相容れない1点を引用または要約する（60字以内）"},
        "rebuttal": {"type": "string", "description": "その1点への反論。200字程度"},
    },
    "required": ["target", "rebuttal"],
    "additionalProperties": False,
}

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "revision": {"type": "string", "enum": ["修正なし", "部分修正"]},
        "statement": {"type": "string", "description": "再反論。200字程度"},
    },
    "required": ["revision", "statement"],
    "additionalProperties": False,
}


def brief_prompt(topic_key: str) -> str:
    return f"""次のお題について、あなたの立場を述べろ。

## お題

{TOPICS[topic_key]}

## 指示

- 中立や両論併記は禁止。どちらかに寄れ。
- 一般論ではなく、あなたの価値観のどこからその立場が出てくるのかを書け。
"""


def rebuttal_prompt(topic_key: str, own: dict, opp: dict) -> str:
    return f"""ディベートの反論フェーズだ。

## お題

{TOPICS[topic_key]}

## あなたが立てた立場

{own['stance']}
{own['reasoning']}

## 相手の立場

{opp['stance']}
{opp['reasoning']}

## 指示

相手の主張のうち、あなたにとって最も相容れない1点だけに集中して反論しろ。
論点を広げるな。相手が実際に言っていることに対して反論しろ。
"""


def final_prompt(topic_key: str, own: dict, own_reb: dict, opp_reb: dict) -> str:
    return f"""ディベートの再反論フェーズだ。ここで終わる。

## お題

{TOPICS[topic_key]}

## あなたの立場

{own['stance']}
{own['reasoning']}

## あなたが相手に投げた反論

{own_reb['rebuttal']}

## 相手からあなたへの反論

（相手が突いてきた点）{opp_reb['target']}
{opp_reb['rebuttal']}

## 指示

まず自分の立場を「修正なし」か「部分修正」かで宣言し、そのうえで応答しろ。
相手の反論に一理あると思ったなら、そう認めたうえで部分修正しろ。見栄を張るな。
"""
