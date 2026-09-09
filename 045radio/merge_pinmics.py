#!/usr/bin/env python3
"""
ピンマイク2本のWhisperCSVをTC順にマージし、csvtoxml 入力フォーマットで出力。

入力:
  045_高野_whisper.csv (Speaker Name, Start Time, End Time, Text)
  045_左地_whisper.csv (同上)

出力:
  045_whisper_merged.csv (Speaker Name, イン点, アウト点, 文字起こし, 色選択)
    - 両ピンマイクの発話を時間順にソート
    - HALLUCINATION_FILTERED 行は除外
    - 色: 高野=Lavender, 左地=Violet
    ★このファイルはTC厳密のまま。荒編とDaVinci流し込みはこれを読む。

  045_whisper_merged_clean.csv / _read.md / _cleanup_audit.json
    - 読み物として成立させるための後処理（下記「クロストーク除去の2層」）
    - RUN_CLEANUP = False で無効化できる

クロストーク除去の2層:
  層1 = 音（vad_segments.py, DOMINANCE_DB=6.0）
    自マイクが相手より6dB以上大きい区間だけを残す。相手の声漏れはWhisperに
    届く前に物理的に消える。3dBだと声漏れまで拾って両マイクが同じ発話を
    二重に書き起こす事故になる（037radioで実証済み）。
  層2 = テキスト（dialogue_cleanup.py, 下記）
    層1を通り抜けた分と、TC順ソートそのものが壊す読みやすさを直す。
    エコー除去 → 相槌吸収 → 同一話者マージ の順（順序に意味がある）。
    層1で拾いきれないのは主にMAI-Transcribeルート。mlx-whisperルートでは
    エコー検出0件だった（045実測）＝層1が効いている証拠。
"""
import csv
import importlib.util
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent

# ===== エピソード固有設定 =====
EPISODE = "045"
EDIT_DIR = Path("/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/045_高野左地/045edit")
INPUTS = [
    (EDIT_DIR / "045_高野_whisper.csv", "高野", "Lavender"),  # Tr1
    (EDIT_DIR / "045_左地_whisper.csv", "左地", "Violet"),    # Tr2
]
RUN_CLEANUP = True
# 正本は claude-config 側（Claude Code / Codex / Antigravity 共通、
# MAI-Transcribeルートも同じものを使う）。ここは呼ぶだけで再実装しない。
CLEANUP_MODULE = Path.home() / "src/claude-config/skills/mai-transcribe/scripts/dialogue_cleanup.py"
CLEANUP_FPS = 25.0
# ===============================
OUTPUT = EDIT_DIR / f"{EPISODE}_whisper_merged.csv"


def parse_tc(tc: str) -> int:
    """TC文字列 → 25fps基準のフレーム数（ソート用）"""
    parts = tc.strip().replace(";", ":").split(":")
    h, m, s, f = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return ((h * 3600 + m * 60 + s) * 25) + f


def main():
    rows = []
    skipped = 0
    for path, speaker, color in INPUTS:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                text = r["Text"].strip()
                if "[HALLUCINATION_FILTERED]" in text or "[ERROR" in text:
                    skipped += 1
                    continue
                if not text:
                    skipped += 1
                    continue
                rows.append({
                    "Speaker Name": speaker,
                    "イン点": r["Start Time"],
                    "アウト点": r["End Time"],
                    "文字起こし": text,
                    "色選択": color,
                    "_sort": parse_tc(r["Start Time"]),
                })

    rows.sort(key=lambda r: r["_sort"])
    for r in rows:
        del r["_sort"]

    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"],
        )
        writer.writeheader()
        writer.writerows(rows)

    speaker_count = {}
    for r in rows:
        speaker_count[r["Speaker Name"]] = speaker_count.get(r["Speaker Name"], 0) + 1

    print(f"出力: {OUTPUT.name}")
    print(f"  total: {len(rows)} rows  (skipped: {skipped})")
    for sp, n in speaker_count.items():
        print(f"  {sp}: {n}")

    if RUN_CLEANUP:
        run_cleanup()


def load_cleanup():
    """dialogue_cleanup を絶対パスで読む。

    見つからないときは黙って素通りせず落とす。エピソード用スクリプトは
    もともと Dropbox 実パスも venv 実パスも直書きしている前提なので、
    ここだけ「無ければスキップ」にすると、荒編済みだと思って読んだCSVが
    実は未処理、という気づけない失敗になる。"""
    if not CLEANUP_MODULE.is_file():
        raise SystemExit(
            f"dialogue_cleanup.py が見つからない: {CLEANUP_MODULE}\n"
            "claude-config を clone していないマシンなら RUN_CLEANUP = False にして、"
            "その場合 merged CSV は未クリーンアップ（相槌が発話の途中に割り込んだまま）だと承知して使う。"
        )
    spec = importlib.util.spec_from_file_location("dialogue_cleanup", CLEANUP_MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dialogue_cleanup"] = module
    spec.loader.exec_module(module)
    return module


def run_cleanup():
    dc = load_cleanup()
    rows, fieldnames = dc.read_csv(OUTPUT, CLEANUP_FPS)
    result = dc.clean(rows, fps=CLEANUP_FPS)

    clean_csv = OUTPUT.with_name(f"{OUTPUT.stem}_clean.csv")
    read_md = OUTPUT.with_name(f"{OUTPUT.stem}_read.md")
    audit = OUTPUT.with_name(f"{OUTPUT.stem}_cleanup_audit.json")

    dc.write_csv(result.rows, clean_csv, fieldnames)
    dc.write_markdown(result.rows, read_md, keep_interjections=False, title=OUTPUT.stem)
    audit.write_text(json.dumps({
        "source": str(OUTPUT),
        "stats": result.stats,
        "dropped_echoes": result.dropped_echoes,
        "absorbed_interjections": result.absorbed_interjections,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    s = result.stats
    print(f"クリーンアップ: {s['rows_in']} 行")
    print(f"  エコー除去(クロストーク): -{s['echoes_removed']}")
    print(f"  相槌吸収:                 -{s['interjections_absorbed']}")
    print(f"  同一話者マージ後:          {s['rows_after_merge']} 行")
    print(f"  → {clean_csv.name} / {read_md.name} / {audit.name}")


if __name__ == "__main__":
    main()
