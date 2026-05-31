# 039回 セットアップ手順

プラッと Whisper パイプライン（Adobe非依存版）。
038radio/ をベースに 039用に書き換えた**収録前の暫定セットアップ**。

## ⚠️ 収録後に必ず確認する2点（暫定値が入っている）

進捗シート（episode 39）より:
- ゲスト: **木崎伸也 / 朴沙羅**
- 収録日: **2026/06/05** / 収録場所: 国立競技場・神宮外苑

1. **WAVファイル名**: 暫定で `260605_001_Tr1.WAV` / `260605_001_Tr2.WAV` と命名（YYMMDD規約からの推測）。実ファイル名を確認して全スクリプトの定数を合わせる。
2. **Tr1/Tr2 ↔ 話者の対応**: 暫定で **Tr1=木崎 / Tr2=朴**（シートのguest順）。
   **これは推測。** 038では「シート順=重田,石塚」だったが実際は Tr1=石塚 だった前例あり。
   収録音源を聞いて、どちらのピンマイクがどちらかを必ず確認すること。

書き換え箇所（038と同じ）:
- `vad_segments.py`: `WAV_TR1/TR2`、出力キー（木崎/朴）
- `transcribe_segments.py`: `WAV_PATHS`、`--speaker` choices、幻覚フィルタ文字列
- `merge_pinmics.py`: 既に `EPISODE="39"`、INPUTS = 木崎/朴
- `csv_to_resolve_timeline.py`: 既に 039設定

## 0. 前提

- venv: `~/.venvs/whisper-asr/`（mlx-whisper 等）
- DaVinci Resolve 起動可能

## 1. 音源を配置

収録後、原本 `~/Dropbox/プラッと/01_プラッと素材/039.../` のWAVを `wav/` にsymlink:

```bash
cd /Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/039radio
SRC="$HOME/Dropbox/プラッと/01_プラッと素材/039XXXX"   # 実フォルダ名に
ln -sf "$SRC/<Tr1実名>.WAV" wav/260605_001_Tr1.WAV
ln -sf "$SRC/<Tr2実名>.WAV" wav/260605_001_Tr2.WAV
```

（symlink名を定数 `260605_001_TrN.WAV` に合わせれば、スクリプト側の書き換え不要）

## 2. パイプライン実行

```bash
cd /Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/039radio

# (1) VAD
~/.venvs/whisper-asr/bin/python vad_segments.py

# (2) Whisper（木崎・朴それぞれ）
~/.venvs/whisper-asr/bin/python transcribe_segments.py --speaker 木崎 --out 木崎_whisper.csv
~/.venvs/whisper-asr/bin/python transcribe_segments.py --speaker 朴 --out 朴_whisper.csv

# (3) 合体CSV
python3 merge_pinmics.py
# → 39_whisper_merged.csv
```

## 3. 荒編（人間作業）

`39_whisper_merged.csv` を開いて不要発話削除＋色分け → `39__S.csv` で保存。
色: 連続同色=1ブロック、`GAP_N`=空白。

## 4. DaVinci Resolveに流し込み

Media Pool に `039` フォルダ作成＋Tr1/Tr2 WAV取込 → Console Py3 で:

```python
exec(open("/Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/039radio/csv_to_resolve_timeline.py", encoding="utf-8").read())
```

→ `39__S_api` タイムライン生成。

## 参照

- 038radio/ : 直近の動作実績（石塚/重田）
- 037radio/ : 初回動作確認
