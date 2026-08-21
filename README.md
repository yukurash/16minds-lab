# 16minds-lab

[16minds-plugin](https://github.com/yukurash/16minds-plugin) の 16 人格を総当たりで走らせ、
**適性表**と**相性表**を実測するためのベンチキット。

プラグインの `/minds` は、お題が何であろうと 16 タイプ全員を呼ぶ。名簿はあるが配役がない。
その配役表をデータで作るのがこのリポジトリの目的で、結果は `casting.json` としてプラグイン側の
`/cast` と `--rival` に渡る。

| 実験 | 内容 | 規模 |
|---|---|---|
| 適性表 | 16 タイプ × 8 タスク × 3 反復 | 384 セル |
| 相性表 | 16C2 = 120 ペアのディベート総当たり | 約 616 コール |

手順・採点基準・封印ハッシュは [RULES.md](RULES.md) に、実験を回す**前**に固定してある。

## 題材

`yukurash.github.io` の `index.html`（単一ファイル 799 行）。実在のコードに、レビュー能力を
測るための欠陥を 4 件だけ仕込んだスナップショットを使う。
仕込みの内容は実験完了まで封印し、ハッシュのみ RULES.md に先出ししている。

- 固定スナップショット: [yukurash.github.io#6](https://github.com/yukurash/yukurash.github.io/pull/6)（Draft・マージしない）

## 使い方

```bash
git clone https://github.com/yukurash/16minds-lab.git
cd 16minds-lab
git clone --depth 1 https://github.com/yukurash/16minds-plugin.git .plugin-src
pip install -r requirements.txt
```

```bash
# 適性表
python harness/run_fit.py --repeats 3
python harness/judge.py fit --slot main

# 相性表
python harness/run_pair.py --topic portfolio_failures --pairs pilot
python harness/run_pair.py --topic portfolio_failures --pairs all
python harness/judge.py pair --topic portfolio_failures

# 図
python harness/figures.py
```

実行には Claude Code CLI（サブスクリプション認証）が要る。API キーは使わない。
同じセルは `results/raw/` にキャッシュされ、途中で止めても再開できる。

## 構成

```
RULES.md            事前登録（採点基準・封印ハッシュ）
harness/
  claudecall.py     claude -p のクリーンルーム実行 + キャッシュ
  personas.py       agents/<type>.md → system prompt
  tasks_fit.py      適性表の 8 タスク
  tasks_pair.py     相性表のペア戦 3 フェーズ
  run_fit.py        適性グリッドのランナー
  run_pair.py       ペア総当たりのランナー
  judge.py          匿名化・シャッフル・採点
  figures.py        ヒートマップ
fixtures/           入力の固定スナップショットと正解リスト（正解は実験完了まで封印）
results/            生ログと集計
```

## これは何ではないか

MBTI の診断でも、人間の性格について何かを主張するものでもない。
同一モデルの上でプロンプトだけが違う 16 条件を比べているだけである。

MIT License
