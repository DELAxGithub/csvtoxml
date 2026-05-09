#!/usr/bin/env python3
"""編集指示書(SP2_編集指示書.md) のブロック範囲をCSVのA列(色選択)に転写する.

指示書の各「▶ ブロックXX」セクションには素材テーブルがある:
  | # | 素材 | ファイル | イン点 | アウト点 | 内容 |

ファイル列の【前】【後】で対象CSVを振り分け、ブロックごとに色を割り当て、
そのブロック内の素材IN-OUT範囲と重なる行のA列に色を書く。
"""

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).parent
INSTR_PATH = BASE_DIR / "SP2_編集指示書_v2.md"
FRONT_CSV = BASE_DIR / "プラッと粗編 - SP2_front_荒編後_Formatted_for_XML.csv"
BACK_CSV = BASE_DIR / "プラッと粗編 - SP2_back_荒編後_Formatted_for_XML.csv"
FRONT_OUT = BASE_DIR / "プラッと粗編 - SP2_front_荒編後_Formatted_for_XML_colored.csv"
BACK_OUT = BASE_DIR / "プラッと粗編 - SP2_back_荒編後_Formatted_for_XML_colored.csv"

FPS = 24.0

COLOR_PALETTE = [
    "Violet", "Rose", "Mango", "Yellow", "Lavender", "Caribbean",
    "Tan", "Forest", "Blue", "Purple", "Teal", "Brown", "Gray",
    "Iris", "Cerulean", "Magenta",
]


@dataclass
class Material:
    num: str  # "1", "40b", "32b" など
    file: str  # "前" or "後"
    in_sec: float
    out_sec: float
    in_tc: str
    out_tc: str


@dataclass
class Block:
    name: str
    materials: list[Material] = field(default_factory=list)


def tc_to_seconds(tc: str) -> float:
    parts = tc.replace(";", ":").split(":")
    nums = [int(p) for p in parts if p.strip().lstrip("-").isdigit()]
    if len(nums) == 4:
        return nums[0] * 3600 + nums[1] * 60 + nums[2] + nums[3] / FPS
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0.0


def parse_instructions(path: Path) -> list[Block]:
    """指示書MDからブロック+素材リストを抽出。"""
    blocks: list[Block] = []
    current: Block | None = None

    block_re = re.compile(r"^####\s*▶\s*(.+)$")
    # | 1 | ... | 【前】 | 00:07:46:01 | 00:08:04:21 | ... |
    # v2では | **40b** | のように 数字+英字 + **ボールド** もある
    row_re = re.compile(
        r"^\|\s*\**\s*(\w+)\s*\**\s*\|\s*[^|]+\|\s*【(前|後)】\s*\|\s*([\d:]+)\s*\|\s*([\d:]+(?:頃)?)\s*\|"
    )

    in_cut_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        # カット素材セクションに入ったら以降は無視
        if line.startswith("## ■ カット素材"):
            in_cut_section = True
            current = None
            continue
        if line.startswith("## ") and in_cut_section:
            in_cut_section = False
        if in_cut_section:
            continue

        m = block_re.match(line)
        if m:
            current = Block(name=m.group(1).strip())
            blocks.append(current)
            continue

        # ブロックヘッダなしでも テーブルだけある章（OPなど）は仮想ブロックを作る
        rm = row_re.match(line)
        if rm:
            num = rm.group(1)
            file = rm.group(2)
            in_tc = rm.group(3).strip()
            out_tc_raw = rm.group(4).strip().replace("頃", "")
            try:
                in_sec = tc_to_seconds(in_tc)
                out_sec = tc_to_seconds(out_tc_raw)
            except Exception:
                continue
            mat = Material(
                num=num, file=file,
                in_sec=in_sec, out_sec=out_sec,
                in_tc=in_tc, out_tc=out_tc_raw,
            )
            if current is None:
                current = Block(name=f"(unnamed before #{num})")
                blocks.append(current)
            current.materials.append(mat)

    # 空ブロックは除去
    return [b for b in blocks if b.materials]


def apply_colors_to_csv(csv_path: Path, out_path: Path, file_label: str, blocks: list[Block]) -> None:
    """CSVに色を書き込む。

    各ブロックの全素材を見て、対象ファイル(file_label)の素材があれば
    その素材のIN-OUT範囲と重なるCSV行のA列にブロックの色を書く。
    """
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return
    header = rows[0]
    data = rows[1:]

    # CSVのIN/OUTを秒に変換しておく
    parsed: list[tuple[float, float]] = []
    for r in data:
        try:
            parsed.append((tc_to_seconds(r[1]), tc_to_seconds(r[2])))
        except Exception:
            parsed.append((0.0, 0.0))

    # ブロックを順番に処理し、対象ファイルの素材があるブロックだけ色を割り当て
    # 「直近に使った色は避ける」方式: 未使用色を優先、全色使ったら最も古い色を再利用
    matched_count = 0
    block_summary: list[tuple[str, str, int]] = []
    last_used: dict[str, int] = {}  # 色 → 最後に使った順序
    used_order = 0

    for block in blocks:
        materials_for_file = [m for m in block.materials if m.file == file_label]
        if not materials_for_file:
            continue

        # 未使用色 > 最も古く使った色 の順で選ぶ
        unused = [c for c in COLOR_PALETTE if c not in last_used]
        if unused:
            color = unused[0]
        else:
            color = min(COLOR_PALETTE, key=lambda c: last_used[c])
        last_used[color] = used_order
        used_order += 1
        block_hits = 0

        for mat in materials_for_file:
            for i, (row_in, row_out) in enumerate(parsed):
                # 重なる: 行IN ≤ 素材OUT AND 素材IN ≤ 行OUT
                if row_in <= mat.out_sec and mat.in_sec <= row_out:
                    if not data[i][0]:  # 既に色が入ってない場合のみ
                        data[i][0] = color
                        block_hits += 1
                        matched_count += 1

        block_summary.append((block.name, color, block_hits))

    # 出力
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)

    print(f"\n=== {file_label}半 ({csv_path.name}) ===")
    print(f"  → {out_path.name}: {len(data)}行中 {matched_count}行に色付け")
    for name, color, hits in block_summary:
        print(f"    [{color:10s}] {hits:3d}行  {name}")


def main():
    print("指示書を解析中...")
    blocks = parse_instructions(INSTR_PATH)
    total_mats = sum(len(b.materials) for b in blocks)
    print(f"  {len(blocks)} ブロック / {total_mats} 素材を抽出")

    apply_colors_to_csv(FRONT_CSV, FRONT_OUT, "前", blocks)
    apply_colors_to_csv(BACK_CSV, BACK_OUT, "後", blocks)


if __name__ == "__main__":
    main()
