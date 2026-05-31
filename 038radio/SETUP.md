# 038回 セットアップ手順

プラッと Whisper パイプライン（Adobe非依存版）。
037radio/ で動作確認済みのスクリプトを 038radio/ にコピーし、038用（話者: 石塚 / 重田）に書き換え済み。

## 0. 前提

- Mac Studio (M1 Ultra 推奨) / このMBPでも可
- venv: `~/.venvs/whisper-asr/` に mlx-whisper 等インストール済み
- DaVinci Resolve 起動可能

## 1. 音源（配置済み）

`wav/` に Dropbox 原本へのシンボリックリンクを作成済み:

```
038radio/wav/
  260531_001_Tr1.WAV → 石塚ピンマイク
  260531_001_Tr2.WAV → 重田ピンマイク
```

原本: `~/Dropbox/プラッと/01_プラッと素材/038重田石塚/`

## 2. スクリプトの定数（書き換え済み）

各スクリプトは 038用に設定済み。

- `vad_segments.py`: `WAV_TR1/TR2` = 260531_001_Tr1/Tr2.WAV、出力キー = 石塚 / 重田
- `transcribe_segments.py`: `WAV_PATHS`、`--speaker` choices = 石塚 / 重田
- `merge_pinmics.py`: `EPISODE="38"`、INPUTS = 石塚(Lavender) / 重田(Violet)
- `csv_to_resolve_timeline.py`: `CSV_PATH`/`TIMELINE_NAME=38__S_api`/`FOLDER_NAME=038`/`TR1_CLIP`/`TR2_CLIP`

## 3. パイプライン実行

```bash
cd /Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/038radio

# (1) VAD: ピンマイク優位差分で発話セグメント抽出（初回はffmpegで16kHz変換も自動）
~/.venvs/whisper-asr/bin/python vad_segments.py

# (2) Whisper書き起こし（石塚・重田それぞれ10〜15分かかる）
~/.venvs/whisper-asr/bin/python transcribe_segments.py --speaker 石塚 --out 石塚_whisper.csv
~/.venvs/whisper-asr/bin/python transcribe_segments.py --speaker 重田 --out 重田_whisper.csv

# (3) 合体CSV生成（Premiere書き起こし代替・全発話）
python3 merge_pinmics.py
# → 38_whisper_merged.csv が生成される
```

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
exec(open("/Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/038radio/csv_to_resolve_timeline.py", encoding="utf-8").read())
```

→ `38__S_api` タイムラインが作られて、Tr1/Tr2 同期で14クリップ程度が並ぶ。

## トラブルシューティング

- **クロストーク誤判定が多い**: `vad_segments.py` の `DOMINANCE_DB=6.0` を 8 や 10 に上げる
- **Whisper幻覚が多い**: `transcribe_segments.py` の `MIN_SEG_SEC=1.5` を 2.0 に上げる、または compression_ratio_threshold を 1.5 に
- **Resolve でブロック化が変**: 荒編CSV `38__S.csv` の色分けを再確認（同色連続が1ブロック）

## 参照

- 037radio/ : 動作確認済み実装
- 037radio/_scratch/ : 試行錯誤の不採用ファイル（EDL/FCPXML/DaVinci内蔵書き起こし）
