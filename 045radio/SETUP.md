# EP045 文字起こしセットアップ

2026-09-03に完走した、EP045 高野孝子 × 左地亮子のローカルWhisper手順。
音声と文字起こしCSVはGitへ入れず、Dropbox側に保持する。

## 入力と話者対応

- `wav/260828_001_Tr1.WAV` → 高野（Dropbox原本へのsymlink）
- `wav/260828_001_Tr2.WAV` → 左地（Dropbox原本へのsymlink）
- 原本: `/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/045_高野左地/`
- 両トラック: mono / 48kHz / 32-bit float / 5,878秒

話者対応は先頭と中盤のpilot文字起こしで確認した。

## 実行

```bash
cd '/Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/045radio'

/Users/delaxpro/.venvs/whisper-asr/bin/python vad_segments.py

/Users/delaxpro/.venvs/whisper-asr/bin/python transcribe_segments.py \
  --speaker 高野 \
  --out '/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/045_高野左地/045edit/045_高野_whisper.csv'

/Users/delaxpro/.venvs/whisper-asr/bin/python transcribe_segments.py \
  --speaker 左地 \
  --out '/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/045_高野左地/045edit/045_左地_whisper.csv'

python3 merge_pinmics.py
```

モデルは `mlx-community/whisper-large-v3-turbo`、VADは6dB優位差分、タイムコードは25fps基準。
pilot時は `transcribe_segments.py` の `--limit` と `--offset` を使用できる。

## 2026-09-03 実行結果

- VAD: 高野 268セグメント / 1,529.2秒、左地 368セグメント / 2,569.9秒
- 話者別CSV: 高野268行、左地368行、エラー0、空欄0
- 幻覚フィルタ除外: 高野4行、左地3行
- merged CSV: `045edit/045_whisper_merged.csv`、629行
- merged内訳: 高野264行、左地365行
- merged QC: 5列ヘッダ、時系列、範囲、話者、空欄、エラーを検査して合格
- Google Sheets: `045_whisper_merged` へ新規投入、ヘッダ込み630行をreadbackして完全一致
- Sheet表示: 先頭1行固定、A:Eフィルタ設定済み
- クリーンアップ（2026-09-09追加、既存のmerged CSVはバイト単位で変化なしを確認済み）:
  629行 → エコー0件 / 相槌2件吸収 → マージ後328行

DaVinciタイムライン作成、内容編集、NA、BGMは今回の対象外。

## クロストーク除去の2層について

`merge_pinmics.py` は merged CSV に続けて `_clean.csv` / `_read.md` /
`_cleanup_audit.json` を出す。層1（音・`DOMINANCE_DB=6.0`）と層2（テキスト・
`dialogue_cleanup.py`）の役割分担と、なぜTC順ソートだけでは読み物にならないのかは
[046radio/SETUP.md](../046radio/SETUP.md#クロストーク除去は2層ある) に書いてある。
045と046で処理は同一。

## 正規ルートは MAI（2026-09-09 決定）

**投入するのは `045_MAIvad_whisper_merged_clean.csv`。** mlx-whisper ルートは削除せず
比較用に残す（Sheets タブ `045_whisper_clean` として併置）。根拠・トレードオフ・見直し条件は
[ADR 0002](../../docs/adr/0002-asr-route-mai-over-local-whisper.md)。

このSETUP.mdの以降の手順は mlx-whisper ルートの実行記録だが、VAD区間・TC基準・
クリーンアップ・Sheets投入の考え方は両ルート共通。
