Premiere CSV と Whisper A/B mic CSV をマージして STEP1_HEADERS 形式の整形済みCSVを生成する。

## 使い方

引数: エピソードディレクトリパス（例: `033radio`）

## 手順

1. 指定ディレクトリ内の CSV ファイルを確認:
   - `*_1.csv`, `*_2.csv` → Premiere CSV（パート1, パート2）
   - `*_Amic.csv` → Whisper A mic CSV（パートごとに1つ）
   - `*_Bmic.csv` → Whisper B mic CSV（パートごとに1つ）

2. ファイルの対応関係を特定:
   - ファイル名の番号やパート番号でペアリング
   - パート1: 最初の Premiere CSV + 最初の Amic + 最初の Bmic
   - パート2: 2番目の Premiere CSV + 2番目の Amic + 2番目の Bmic

3. ディレクトリ内に `output/` フォルダを作成（なければ）

4. 各パートについて Python で実行:
   ```python
   from csvtoxml.core.preprocessor import merge_with_whisper, write_formatted_csv
   from pathlib import Path

   data, speaker_a, speaker_b = merge_with_whisper(
       premiere_csv_path,
       whisper_a_path,
       whisper_b_path,
   )
   output_path = Path("<dir>/output/<premiere_stem>_whisper_merged.csv")
   write_formatted_csv(data, output_path)
   ```

5. 結果を報告:
   - 各パートの Speaker A / Speaker B 名
   - 行数
   - 出力ファイルパス
   - 最初の数行を表示してレイアウトが正しいか確認

## 出力フォーマット

STEP1_HEADERS（7列）:
- 色選択（空欄 = ユーザーが後で手動入力）
- イン点（Premiere TC）
- アウト点（Premiere TC）
- スピーカーネーム（Premiere話者名）
- スピーカーAの文字起こし（Whisper A mic テキスト）
- スピーカーBの文字起こし（Whisper B mic テキスト）
- AやB以外（Premiere オリジナルテキスト）

Speaker A/B は Premiere CSV の出現頻度上位2名から自動判定。
A mic を付けている話者 → E列、B mic を付けている話者 → F列、それ以外 → G列。
