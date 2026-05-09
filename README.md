# csvtoxml

CSV形式の粗編指示書をPremiere Pro用XMLタイムラインに変換するCLIツール。

ポッドキャスト「プラッと」の編集ワークフローで使用中（035〜）。

## ワークフロー

```
Whisper文字起こし → Google Sheets粗編 → 荒編後CSV → csvtoxml → Premiere Pro XML
```

1. Whisperで文字起こしCSVを生成
2. Google Sheetsで粗編（話者・色・GAP区切りを整理）
3. 荒編後CSVをエクスポート
4. `csvtoxml` でテンプレートXMLと合わせてediting XMLを生成
5. Premiere Proにインポート

## インストール

```bash
cd csvtoxml
python3 -m venv .venv
.venv/bin/pip install -e .
```

## 使い方

### CLI

```bash
# 基本
csvtoxml 荒編後.csv template.xml

# 出力先指定
csvtoxml 荒編後.csv template.xml -o output.xml

# GAP間隔を変更（デフォルト5秒）
csvtoxml 荒編後.csv template.xml --gap 3.0
```

### Claude Code スキル

```
/csvtoxml csvtoxml/035radio
```

指定ディレクトリ内の `*_荒編後.csv` を自動検出し、対応するテンプレートXMLとペアにして一括変換。

### Python API

```python
from pathlib import Path
from csvtoxml.writers.premiere import generate_premiere_xml

output_path = generate_premiere_xml(
    csv_path=Path("timeline.csv"),
    template_xml_path=Path("template.xml"),
    gap_seconds=5.0,
)
```

## CSV形式

| Column | Description |
|--------|-------------|
| `Speaker Name` | 話者名（藤井、相馬 等） |
| `イン点` | インポイント（HH:MM:SS:FF） |
| `アウト点` | アウトポイント（HH:MM:SS:FF） |
| `文字起こし` | 文字起こしテキスト |
| `色選択` | Premiere Pro ラベル色 |

### セクション色分けの例

同じ色の連続行が1つのブロックになる。色が変わるとブロックが分かれる。

| 色 | 用途例 |
|----|--------|
| Violet | 導入トーク |
| Rose | トピック1 |
| Mango | トピック2 |
| Caribbean | トピック3 |
| Yellow, Tan, Lavender... | 追加トピック |

### GAPマーカー

色選択に `GAP_N` を指定するとセクション間の区切りになる：

```csv
,00:00:00:00,00:00:10:02,--- 20s GAP ---,GAP_1
```

### CSVサンプル

```csv
Speaker Name,イン点,アウト点,文字起こし,色選択
藤井,00:09:24:00,00:09:26:00,散歩しながらねお話できるなんてね,Violet
相馬,00:09:28:00,00:09:31:00,そうですね。風流なことで。,Violet
,00:00:00:00,00:00:10:02,--- 20s GAP ---,GAP_1
相馬,00:10:27:00,00:10:30:00,最近フォローしてないんですけど、どんなことなさってるか。,Rose
藤井,00:10:28:00,00:10:31:00,でもなんかこれ奇妙なご縁というか,Rose
```

## ディレクトリ構成（エピソード単位）

```
csvtoxml/035radio/
  35_1.xml              # テンプレートXML（Premiereからエクスポート）
  35_2.xml
  35_1_荒編後.csv        # Google Sheetsからエクスポート
  35_2_荒編後.csv
  35_1_荒編後_editing.xml # csvtoxmlで生成 → Premiereにインポート
  35_2_荒編後_editing.xml
```

## 対応ラベル色

Violet, Rose, Mango, Yellow, Lavender, Caribbean, Tan, Forest, Blue, Purple, Teal, Brown, Gray, Iris, Cerulean, Magenta

## 開発

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT License
