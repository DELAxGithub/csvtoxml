# EP046 文字起こしセットアップ

2026-09-03に完走した、EP046 松田俊介 × 土門蘭のローカルWhisper手順。
音声と文字起こしCSVはGitへ入れず、Dropbox側に保持する。

## 入力と話者対応

- `wav/260829_001_Tr1.WAV` → 土門（Dropbox原本へのsymlink）
- `wav/260829_001_Tr2.WAV` → 松田（Dropbox原本へのsymlink）
- 原本: `/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/046_松田土門/`
- 両トラック: mono / 48kHz / 32-bit float / 6,402秒

話者対応はpilot文字起こしで確認した。

## 実行

```bash
cd '/Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/046radio'

/Users/delaxpro/.venvs/whisper-asr/bin/python vad_segments.py

/Users/delaxpro/.venvs/whisper-asr/bin/python transcribe_segments.py \
  --speaker 土門 \
  --out '/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/046_松田土門/046edit/046_土門_whisper.csv'

/Users/delaxpro/.venvs/whisper-asr/bin/python transcribe_segments.py \
  --speaker 松田 \
  --out '/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/046_松田土門/046edit/046_松田_whisper.csv'

python3 merge_pinmics.py
```

モデルは `mlx-community/whisper-large-v3-turbo`、VADは6dB優位差分、タイムコードは25fps基準。
pilot時は `transcribe_segments.py` の `--limit` と `--offset` を使用できる。
`merge_pinmics.py` は merged CSV に続けてクリーンアップ3点も出す（次節）。

## クロストーク除去は2層ある

ピンマイク別録りは、自分のマイクが相手の声も拾う。対策は音とテキストの2段構えで、
**片方だけでは足りない**。

### 層1 — 音（`vad_segments.py`, `DOMINANCE_DB = 6.0`）

自マイクが相手より6dB以上大きいフレームだけを「自分の発話」として残し、それ以外は
Whisperに渡す前に物理的に落とす。

- **3dBにしてはいけない**: 声漏れまで自分の発話として拾い、両マイクが同じ発話を
  二重に書き起こす事故になる（037radioで実証済み）
- 誤判定がまだ多いなら 8 や 10 に上げる。ただし小声の本発話も落ちる
- **これが効いている証拠**: 046のmlx-whisperルートは層2のエコー検出が **0件**。
  一方MAI-Transcribeルートは同じ音源で **23件** 出た（MAIの方が弱い声漏れまで
  文字にするため）。層1の閾値はルートによって足りたり足りなかったりする

### 層2 — テキスト（`dialogue_cleanup.py`）

層1を通り抜けたクロストークと、**TC順ソートそのものが壊す読みやすさ**を直す。
`merge_pinmics.py` が自動で呼ぶ（`RUN_CLEANUP = False` で無効化）。

TC順ソートが壊すもの: Aが6秒喋っている最中にBが2.1秒地点で相槌を打つと、開始TC順の
並びは必ずAの文の途中にBを差し込む。しかもその後の同一話者マージは「並びとして
隣接」しか繋がないので、**Aの前半と後半は二度と繋がらない**。3人鼎談だと割り込み源が
2倍になる。

処理は3段、**順序に意味がある**:

1. **エコー除去** — 別話者・**時間的に連続**（重なるか0.5秒以内）・類似度0.6超 → 長い方を残す。
   混線は「1つの音を2回書いた」ものなので連続しているはず。開始TCの近さだけで判定すると、
   3人以上で別々の人が数秒差で「うん」と言っただけの箇所を混線と誤判定して片方を消す
2. **相槌吸収** — 相槌辞書だけで構成されている（先頭が相槌なだけの実発言は対象外）
   かつ 他話者の実発話（20文字超）と時間的に重なる → 抜く
3. **同一話者マージ** — 1,2で間の行が消えて初めて隣接になるので、ここで繋がる

出力（**元の `046_whisper_merged.csv` は一切書き換えない**。荒編とDaVinci流し込みは
引き続きTC厳密なこちらを読む）:

| ファイル | 用途 |
|---|---|
| `046_whisper_merged_clean.csv` | 同じ5列スキーマ。読みやすさ重視の粒度 |
| `046_whisper_merged_read.md` | 話者ブロックの読み物。相槌は落とす |
| `046_whisper_merged_cleanup_audit.json` | **消した行の全記録**。判定ミスを手で戻せる |

単体でも走る（fpsは対象タイムラインに合わせる）:

```bash
python3 ~/src/claude-config/skills/mai-transcribe/scripts/dialogue_cleanup.py \
  046_whisper_merged.csv --fps 25
```

直せないもの: **1行の中に混入したクロストーク**（`...松田さんとは違うか。違います。`
の「違います。」が相手の発話）。これは行の並べ替えでは直らないので層1の閾値を上げる。

## 2026-09-03 実行結果

- VAD: 土門 292セグメント / 1,972.0秒、松田 334セグメント / 2,007.5秒
- 話者別CSV: 土門292行、松田334行、エラー0、空欄0
- 幻覚フィルタ除外: 土門7行、松田5行
- merged CSV: `046edit/046_whisper_merged.csv`、614行
- merged内訳: 土門285行、松田329行
- クリーンアップ（2026-09-09追加、既存のmerged CSVはバイト単位で変化なしを確認済み）:
  614行 → エコー0件 / 相槌9件吸収 → マージ後361行
- merged QC: 5列ヘッダ、時系列、範囲、話者、空欄、エラーを検査して合格
- Google Sheets: `046_whisper_merged` へ新規投入、ヘッダ込み615行をreadbackして完全一致
- Sheet表示: 先頭1行固定、A:Eフィルタ設定済み

DaVinciタイムライン作成、内容編集、NA、BGMは今回の対象外。
