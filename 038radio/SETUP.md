# 038回 セットアップ手順

プラッと Whisper パイプライン（Adobe非依存版）。
037radio/ で動作確認済みのスクリプトを 038radio/ にコピーした状態。

## 0. 前提

- Mac Studio (M1 Ultra 推奨)
- venv: `~/.venvs/whisper-asr/` に mlx-whisper 等インストール済み
- DaVinci Resolve 起動可能

## 1. 音源を配置

```
038radio/wav/
  XXXXX_001_Tr1.WAV  ← 千葉ピンマイク
  XXXXX_001_Tr2.WAV  ← 東島ピンマイク
```

## 2. 各スクリプトの定数を 038 用に書き換える

`★038で書き換え` コメントが付いている定数だけ。

### `vad_segments.py`

```python
WAV_TR1 = "XXXXX_001_Tr1.WAV"   # 実ファイル名に
WAV_TR2 = "XXXXX_001_Tr2.WAV"
```

### `transcribe_segments.py`

```python
WAV_PATHS = {
    "千葉": WAV_DIR / "XXXXX_001_Tr1.WAV",
    "東島": WAV_DIR / "XXXXX_001_Tr2.WAV",
}
```

### `merge_pinmics.py`

```python
EPISODE = "38"
```

### `csv_to_resolve_timeline.py`

```python
CSV_PATH = "/Users/delaxstudio/src/70_プラッと/platto-automation/csvtoxml/038radio/38__S.csv"
TIMELINE_NAME = "38__S_api"
FOLDER_NAME = "038"               # DaVinciメディアプール内のフォルダ名
TR1_CLIP = "XXXXX_001_Tr1.WAV"
TR2_CLIP = "XXXXX_001_Tr2.WAV"
```

## 3. パイプライン実行

```bash
cd /Users/delaxstudio/src/70_プラッと/platto-automation/csvtoxml/038radio

# (1) VAD: ピンマイク優位差分で発話セグメント抽出（初回はffmpegで16kHz変換も自動）
~/.venvs/whisper-asr/bin/python vad_segments.py

# (2) Whisper書き起こし（千葉・東島それぞれ10〜15分かかる）
~/.venvs/whisper-asr/bin/python transcribe_segments.py --speaker 千葉 --out 千葉_whisper.csv
~/.venvs/whisper-asr/bin/python transcribe_segments.py --speaker 東島 --out 東島_whisper.csv

# (3) 合体CSV生成（Premiere書き起こし代替・全発話）
python3 merge_pinmics.py
# → 38_whisper_merged.csv が生成される
```

### (2 alt) ElevenLabs Scribe で書き起こす場合

mlx-whisper の代わりに ElevenLabs Scribe API を使う。日本語の句読点・固有名詞精度が高い。
試算: 1.5h × 2人 ≒ 3h ≒ $1.2/月（$0.40/h ベース）。

```bash
# APIキーをセット（.env.tpl に ELEVENLABS_API_KEY 追加済み）
cd /Users/delaxstudio/src/70_プラッと/platto-automation
op inject -i .env.tpl -o .env && source .env
cd csvtoxml/038radio

# 接続テスト（先頭3セグメントだけ叩く）
~/.venvs/whisper-asr/bin/python transcribe_segments_scribe.py --speaker 千葉 --limit 3

# 本番（出力ファイル名を _whisper.csv に揃えれば merge_pinmics は無改修）
~/.venvs/whisper-asr/bin/python transcribe_segments_scribe.py --speaker 千葉 --out 千葉_whisper.csv
~/.venvs/whisper-asr/bin/python transcribe_segments_scribe.py --speaker 東島 --out 東島_whisper.csv
```

実行後に `audio: X min / est cost: $Y` を表示するのでコスト確認可。Whisperと比較したい場合は `--out 千葉_scribe.csv` で別名保存して両方の出力を見比べる。

## 4. 荒編（人間作業）

`38_whisper_merged.csv` を Numbers / Excel で開いて、不要発話を削除し色分けする。
完成版を `38__S.csv` として保存。

色マッピングルール（37 と同じ）:
- 連続する同じ色 → 1ブロックに統合
- `GAP_N` 色 → タイムライン上の空白
- 結果: 14ブロック + 13ギャップ 程度の構造

## 5. DaVinci Resolveに流し込み

1. DaVinci Resolveでプロジェクトを開く
2. Media Pool に `038` フォルダを作成、Tr1/Tr2 のWAVを取り込む
3. `Workspace > Console > Py3` を開く
4. 以下を実行:

```python
exec(open("/Users/delaxstudio/src/70_プラッと/platto-automation/csvtoxml/038radio/csv_to_resolve_timeline.py", encoding="utf-8").read())
```

→ `38__S_api` タイムラインが作られて、Tr1/Tr2 同期で14クリップ程度が並ぶ。

## トラブルシューティング

- **クロストーク誤判定が多い**: `vad_segments.py` の `DOMINANCE_DB=6.0` を 8 や 10 に上げる
- **Whisper幻覚が多い**: `transcribe_segments.py` の `MIN_SEG_SEC=1.5` を 2.0 に上げる、または compression_ratio_threshold を 1.5 に
- **Resolve でブロック化が変**: 荒編CSV `38__S.csv` の色分けを再確認（同色連続が1ブロック）

## 参照

- 037radio/ : 動作確認済み実装
- 037radio/_scratch/ : 試行錯誤の不採用ファイル（EDL/FCPXML/DaVinci内蔵書き起こし）
