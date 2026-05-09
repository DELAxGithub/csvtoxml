#!/usr/bin/env python3
"""SP2radio: ミックス書き起こし(Sp1-4.csv) × 個別マイク(otsuru/yamamoto/yoshida.csv) マージスクリプト.

Sp*.csv のタイムコードをバックボーンに、各スピーカーの発言テキストを
対応する個別マイクCSVから引っ張って置換し、荒編後CSVを出力する。
"""

import csv
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# ── 設定 ──────────────────────────────────────────────

FPS = 24.0

SPEAKER_MIC_MAP = {
    "大津留": ("otsuru.csv", "大津留"),
    "山本": ("yamamoto.csv", "山本"),
    "吉田": ("yoshida.csv", "吉田"),
}

SPEAKER_ALIAS = {"話者 1": "不明"}

COLOR_PALETTE = [
    "Violet", "Rose", "Mango", "Caribbean", "Yellow",
    "Lavender", "Tan", "Forest", "Blue", "Purple",
]

MATCH_TOLERANCE_SEC = 10.0
MATCH_TOLERANCE_WIDE_SEC = 15.0
ECHO_SIMILARITY = 0.6
ECHO_TIME_SEC = 3.0
INTERJECTION_MAX_CHARS = 4
CONSECUTIVE_MERGE_GAP_SEC = 3.0
GAP_THRESHOLD_SEC = 20.0
SPLIT_SEC = 2 * 3600.0  # 02:00:00:00

BASE_DIR = Path(__file__).parent

# ── データ構造 ─────────────────────────────────────────


@dataclass
class Row:
    speaker: str
    start_tc: str
    end_tc: str
    start_sec: float
    end_sec: float
    text: str
    color: str = ""
    is_gap: bool = False


# ── ユーティリティ ──────────────────────────────────────


def tc_to_seconds(tc: str) -> float:
    """HH:MM:SS:FF (24fps) → seconds."""
    if not tc:
        return 0.0
    parts = tc.replace(";", ":").split(":")
    nums = [int(p) for p in parts if p.strip().isdigit()]
    if len(nums) == 4:
        return nums[0] * 3600 + nums[1] * 60 + nums[2] + nums[3] / FPS
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return 0.0


def strip_suffix(name: str) -> str:
    """'大津留1' → '大津留', 'D3' → 'D'."""
    return re.sub(r"[1-4]$", "", name.strip())


def normalize_speaker(name: str) -> str:
    s = strip_suffix(name)
    return SPEAKER_ALIAS.get(s, s)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def deduplicate_texts(texts: list[str]) -> str:
    """マッチした複数テキストを連結する際、重複を除去。

    隣接テキスト間の類似度が高い場合はスキップし、
    同一テキストの完全重複も除去する。
    """
    if not texts:
        return ""
    if len(texts) == 1:
        return texts[0]

    seen: list[str] = [texts[0]]
    for t in texts[1:]:
        # 完全一致
        if t in seen:
            continue
        # 直前テキストとの類似度チェック
        if similarity(t, seen[-1]) > 0.7:
            # 長い方を採用
            if len(t) > len(seen[-1]):
                seen[-1] = t
            continue
        # 全既存テキストに含まれるサブストリングか
        is_sub = False
        for s in seen:
            if t in s or s in t:
                if len(t) > len(s):
                    seen[seen.index(s)] = t
                is_sub = True
                break
        if not is_sub:
            seen.append(t)

    return " ".join(seen)


def remove_sentence_duplicates(text: str) -> str:
    """長文テキスト内のセンテンス単位の重複を除去。

    「。」で区切った文を順に見て、既出の文（類似度>0.8）をスキップ。
    """
    if len(text) < 40:
        return text

    # 「。」で分割（末尾の句点は保持）
    raw_sentences = text.split("。")
    sentences: list[str] = []
    for s in raw_sentences:
        s = s.strip()
        if s:
            sentences.append(s + "。")

    if len(sentences) <= 1:
        return text

    seen: list[str] = []
    for s in sentences:
        is_dup = False
        for prev in seen:
            if similarity(s, prev) > 0.8:
                is_dup = True
                break
        if not is_dup:
            seen.append(s)

    result = " ".join(seen)
    # 末尾が「。。」にならないよう
    return result.replace("。。", "。")


# ── CSV読み込み ────────────────────────────────────────


def load_sp_csvs() -> list[Row]:
    """Sp1-4.csv を読み込み、時間順でソートして返す。"""
    rows: list[Row] = []
    for i in range(1, 5):
        path = BASE_DIR / f"Sp{i}.csv"
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            for line in reader:
                if len(line) < 4:
                    continue
                speaker = normalize_speaker(line[0])
                start_tc = line[1].strip()
                end_tc = line[2].strip()
                text = line[3].strip()
                rows.append(Row(
                    speaker=speaker,
                    start_tc=start_tc,
                    end_tc=end_tc,
                    start_sec=tc_to_seconds(start_tc),
                    end_sec=tc_to_seconds(end_tc),
                    text=text,
                ))
    rows.sort(key=lambda r: r.start_sec)
    return rows


def load_individual_csvs() -> dict[str, list[Row]]:
    """個別マイクCSVを読み込み、スピーカー名 → 行リストの辞書で返す。

    各マイクCSVから、対応するスピーカー名の行のみ抽出。
    """
    index: dict[str, list[Row]] = {"大津留": [], "山本": [], "吉田": []}

    for target_speaker, (filename, label) in SPEAKER_MIC_MAP.items():
        path = BASE_DIR / filename
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for line in reader:
                if len(line) < 4:
                    continue
                raw_speaker = normalize_speaker(line[0])
                if raw_speaker != label:
                    continue
                start_tc = line[1].strip()
                end_tc = line[2].strip()
                index[target_speaker].append(Row(
                    speaker=raw_speaker,
                    start_tc=start_tc,
                    end_tc=end_tc,
                    start_sec=tc_to_seconds(start_tc),
                    end_sec=tc_to_seconds(end_tc),
                    text=line[3].strip(),
                ))

    for rows in index.values():
        rows.sort(key=lambda r: r.start_sec)

    return index


# ── テキスト置換 ───────────────────────────────────────



def replace_text(sp_rows: list[Row], individual: dict[str, list[Row]]) -> list[Row]:
    """Spバックボーンのテキストを個別マイクで置換。"""
    result: list[Row] = []
    # 使用済み個別行を追跡（同じ行が複数Sp行にマッチするのを防ぐ）
    used: dict[str, set[int]] = {k: set() for k in individual}

    for sp in sp_rows:
        if sp.speaker not in individual:
            # D, 不明 etc. → そのまま
            result.append(Row(
                speaker=sp.speaker,
                start_tc=sp.start_tc,
                end_tc=sp.end_tc,
                start_sec=sp.start_sec,
                end_sec=sp.end_sec,
                text=sp.text,
            ))
            continue

        candidates = individual[sp.speaker]
        used_set = used[sp.speaker]

        # Pass 1: 通常tolerance（未使用のみ）
        matched = [
            (i, c) for i, c in enumerate(candidates)
            if i not in used_set
            and (sp.start_sec - MATCH_TOLERANCE_SEC)
            <= (c.start_sec + c.end_sec) / 2.0
            <= (sp.end_sec + MATCH_TOLERANCE_SEC)
        ]

        # Pass 2: 広めtolerance + 文字列類似度
        if not matched:
            matched = [
                (i, c) for i, c in enumerate(candidates)
                if i not in used_set
                and (sp.start_sec - MATCH_TOLERANCE_WIDE_SEC)
                <= (c.start_sec + c.end_sec) / 2.0
                <= (sp.end_sec + MATCH_TOLERANCE_WIDE_SEC)
            ]
            if len(matched) > 1:
                matched.sort(key=lambda ic: similarity(sp.text, ic[1].text), reverse=True)
                matched = matched[:1]

        if matched:
            matched.sort(key=lambda ic: ic[1].start_sec)
            # 使用済みマーク
            for idx, _ in matched:
                used_set.add(idx)
            new_text = deduplicate_texts([c.text for _, c in matched if c.text])
        else:
            new_text = sp.text

        result.append(Row(
            speaker=sp.speaker,
            start_tc=sp.start_tc,
            end_tc=sp.end_tc,
            start_sec=sp.start_sec,
            end_sec=sp.end_sec,
            text=new_text,
        ))

    return result


# ── クリーンアップ ─────────────────────────────────────


def remove_echoes(rows: list[Row]) -> list[Row]:
    """隣接行で同じ内容のエコーを除去。"""
    if not rows:
        return rows
    keep = [True] * len(rows)

    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if a.speaker == b.speaker:
            continue
        time_gap = abs(b.start_sec - a.start_sec)
        if time_gap > ECHO_TIME_SEC:
            continue
        sim = similarity(a.text, b.text)
        if sim > ECHO_SIMILARITY:
            # 短い方を除去
            if len(a.text) < len(b.text):
                keep[i] = False
            else:
                keep[i + 1] = False

    return [r for r, k in zip(rows, keep) if k]


def filter_interjections(rows: list[Row]) -> list[Row]:
    """短い相槌を除去。"""
    if not rows:
        return rows
    keep = [True] * len(rows)

    for i, r in enumerate(rows):
        if len(r.text) > INTERJECTION_MAX_CHARS:
            continue
        # 前後の行に長い発言があるか
        for j in (i - 1, i + 1):
            if 0 <= j < len(rows):
                other = rows[j]
                if other.speaker != r.speaker and len(other.text) > 20:
                    time_gap = abs(r.start_sec - other.start_sec)
                    if time_gap < 3.0:
                        keep[i] = False
                        break

    return [r for r, k in zip(rows, keep) if k]


def merge_consecutive(rows: list[Row]) -> list[Row]:
    """同一スピーカーの連続行をマージ。"""
    if not rows:
        return rows
    merged: list[Row] = [Row(
        speaker=rows[0].speaker,
        start_tc=rows[0].start_tc,
        end_tc=rows[0].end_tc,
        start_sec=rows[0].start_sec,
        end_sec=rows[0].end_sec,
        text=rows[0].text,
    )]

    for r in rows[1:]:
        prev = merged[-1]
        gap = r.start_sec - prev.end_sec
        if r.speaker == prev.speaker and gap <= CONSECUTIVE_MERGE_GAP_SEC:
            prev.end_tc = r.end_tc
            prev.end_sec = r.end_sec
            # 重複テキスト排除しつつ連結
            prev.text = deduplicate_texts([prev.text, r.text])
        else:
            merged.append(Row(
                speaker=r.speaker,
                start_tc=r.start_tc,
                end_tc=r.end_tc,
                start_sec=r.start_sec,
                end_sec=r.end_sec,
                text=r.text,
            ))

    return merged


def insert_gaps(rows: list[Row]) -> list[Row]:
    """大きな無音区間にGAPマーカーを挿入。"""
    if not rows:
        return rows
    result: list[Row] = [rows[0]]
    gap_count = 0

    for i in range(1, len(rows)):
        gap = rows[i].start_sec - rows[i - 1].end_sec
        if gap > GAP_THRESHOLD_SEC:
            gap_count += 1
            result.append(Row(
                speaker="",
                start_tc="00:00:00:00",
                end_tc="00:00:10:02",
                start_sec=0,
                end_sec=0,
                text=f"--- {int(gap)}s GAP ---",
                is_gap=True,
                color=f"GAP_{gap_count}",
            ))
        result.append(rows[i])

    return result


def assign_colors(rows: list[Row]) -> list[Row]:
    """GAP境界でカラーパレットを循環。"""
    color_idx = 0
    current_color = COLOR_PALETTE[0]

    for r in rows:
        if r.is_gap:
            color_idx = (color_idx + 1) % len(COLOR_PALETTE)
            current_color = COLOR_PALETTE[color_idx]
        elif not r.color:
            r.color = current_color

    return rows


# ── 出力 ───────────────────────────────────────────────


def write_csv(rows: list[Row], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Speaker Name", "イン点", "アウト点", "文字起こし", "色選択"])
        for r in rows:
            writer.writerow([r.speaker, r.start_tc, r.end_tc, r.text, r.color])
    print(f"  → {path.name}: {len(rows)} 行")


# ── メイン ─────────────────────────────────────────────


def main():
    print("=== SP2radio マージ開始 ===")

    # Phase 1: ロード
    print("Phase 1: CSV読み込み...")
    sp_rows = load_sp_csvs()
    print(f"  Sp backbone: {len(sp_rows)} 行")

    individual = load_individual_csvs()
    for name, rows in individual.items():
        print(f"  {name} (個別マイク): {len(rows)} 行")

    # Phase 2: テキスト置換
    print("Phase 2: テキスト置換...")
    merged = replace_text(sp_rows, individual)

    replaced_count = sum(
        1 for sp, mg in zip(sp_rows, merged)
        if sp.text != mg.text
    )
    print(f"  置換: {replaced_count}/{len(merged)} 行")

    # Phase 3: クリーンアップ
    print("Phase 3: クリーンアップ...")
    n0 = len(merged)
    merged = remove_echoes(merged)
    print(f"  エコー除去: {n0} → {len(merged)}")
    n1 = len(merged)
    merged = filter_interjections(merged)
    print(f"  相槌除去: {n1} → {len(merged)}")
    merged = merge_consecutive(merged)
    print(f"  連結後: {len(merged)} 行")

    # 文レベル重複除去（長文内のセンテンス重複）
    for r in merged:
        r.text = remove_sentence_duplicates(r.text)

    # Phase 4: GAP・色・出力
    print("Phase 4: GAP挿入・色付け・出力...")
    merged = insert_gaps(merged)
    merged = assign_colors(merged)

    # 前後半分割
    front = [r for r in merged if r.is_gap or r.start_sec < SPLIT_SEC]
    back = [r for r in merged if r.is_gap or r.start_sec >= SPLIT_SEC]

    # GAP行は両方に入りうるので、実際のタイムコード位置で再判定
    front_clean: list[Row] = []
    back_clean: list[Row] = []
    last_data_sec = 0.0

    for r in merged:
        if not r.is_gap:
            last_data_sec = r.start_sec

        if r.is_gap:
            # GAP は直前のデータ行の位置で振り分け
            if last_data_sec < SPLIT_SEC:
                front_clean.append(r)
            else:
                back_clean.append(r)
        elif r.start_sec < SPLIT_SEC:
            front_clean.append(r)
        else:
            back_clean.append(r)

    # 後半のGAP番号をリナンバリング
    gap_n = 0
    for r in back_clean:
        if r.is_gap:
            gap_n += 1
            r.color = f"GAP_{gap_n}"

    # 後半の色もリセット
    color_idx = 0
    current_color = COLOR_PALETTE[0]
    for r in back_clean:
        if r.is_gap:
            color_idx = (color_idx + 1) % len(COLOR_PALETTE)
            current_color = COLOR_PALETTE[color_idx]
        elif r.color and not r.color.startswith("GAP"):
            r.color = current_color

    write_csv(front_clean, BASE_DIR / "SP2_front_荒編後.csv")
    write_csv(back_clean, BASE_DIR / "SP2_back_荒編後.csv")

    print("=== 完了 ===")


if __name__ == "__main__":
    main()
