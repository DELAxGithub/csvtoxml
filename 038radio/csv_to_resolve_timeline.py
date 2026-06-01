"""
合体CSV (荒編済み) → DaVinci Resolve タイムラインを直接構築。

ブロック化ロジック:
  - 色（色選択列）が同じ連続行を1ブロックに統合
  - GAP_N 行は タイムライン上のギャップ
  - 結果: 14 blocks + 13 gaps の構造（37__S.csv の場合）

DaVinci Resolve の Workspace > Console > Py3 にペースト or exec で実行する想定。

使い方（コンソール）:
    exec(open("/Users/delaxpro/src/70_プラッと/platto-automation/csvtoxml/038radio/csv_to_resolve_timeline.py", encoding="utf-8").read())
"""

import csv

# ===== 設定 =====
CSV_PATH = "/Users/delaxpro/Dropbox/プラッと/01_プラッと素材/038重田石塚/038edit/38_wh.csv"
TIMELINE_NAME = "038編集_cut"
FOLDER_NAME = "038"
TR1_CLIP = "260531_001_Tr1.WAV"
TR2_CLIP = "260531_001_Tr2.WAV"
CSV_FPS = 25
TIMELINE_TC_OFFSET = "01:00:00:00"  # タイムライン起点（37_編集1davinchi.xml と揃える）
# ================


def tc_to_seconds(tc, fps):
    parts = tc.strip().replace(";", ":").split(":")
    h, m, s, f = map(int, parts)
    return h * 3600 + m * 60 + s + f / fps


def find_folder(folder, name):
    if folder.GetName() == name:
        return folder
    for sub in folder.GetSubFolderList():
        r = find_folder(sub, name)
        if r:
            return r
    return None


def build_blocks(rows, csv_fps):
    """色で集約。GAP_N 行はギャップ扱い。
    戻り値: [{"kind": "block"|"gap", "in_sec": float, "out_sec": float, "color": str}, ...]"""
    segs = []
    cur = None
    for r in rows:
        color = r.get("色選択", "").strip()
        try:
            in_sec = tc_to_seconds(r["イン点"], csv_fps)
            out_sec = tc_to_seconds(r["アウト点"], csv_fps)
        except (KeyError, ValueError):
            continue

        if color.startswith("GAP"):
            if cur is not None:
                segs.append(cur)
                cur = None
            segs.append({"kind": "gap", "in_sec": in_sec, "out_sec": out_sec, "color": color})
            continue

        if cur is None or cur["color"] != color:
            if cur is not None:
                segs.append(cur)
            cur = {"kind": "block", "in_sec": in_sec, "out_sec": out_sec, "color": color}
        else:
            cur["out_sec"] = out_sec  # 末尾を伸ばす
    if cur is not None:
        segs.append(cur)
    return segs


def main():
    project = resolve.GetProjectManager().GetCurrentProject()  # noqa: F821
    mp = project.GetMediaPool()
    folder = find_folder(mp.GetRootFolder(), FOLDER_NAME)
    if folder is None:
        print(f"ERROR: folder '{FOLDER_NAME}' not found")
        return

    clips = folder.GetClipList()
    tr1 = next((c for c in clips if c.GetName() == TR1_CLIP), None)
    tr2 = next((c for c in clips if c.GetName() == TR2_CLIP), None)
    if not (tr1 and tr2):
        print(f"ERROR: clips not found  Tr1={tr1} Tr2={tr2}")
        return

    clip_fps = float(tr1.GetClipProperty("FPS") or 24)
    print(f"clip fps: {clip_fps}")

    tl = mp.CreateEmptyTimeline(TIMELINE_NAME)
    if tl is None:
        print(f"ERROR: failed to create timeline (name conflict?): {TIMELINE_NAME}")
        return
    tl.AddTrack("audio")
    tl_fps = float(tl.GetSetting("timelineFrameRate") or clip_fps)
    print(f"timeline: {tl.GetName()}  tl_fps: {tl_fps}")

    rec_offset_sec = tc_to_seconds(TIMELINE_TC_OFFSET, tl_fps)

    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"rows: {len(rows)}")

    segs = build_blocks(rows, CSV_FPS)
    blocks = [s for s in segs if s["kind"] == "block"]
    gaps = [s for s in segs if s["kind"] == "gap"]
    print(f"segments: {len(segs)}  ({len(blocks)} blocks + {len(gaps)} gaps)")

    # タイムライン rec_pos を累積で計算
    rec_pos_sec = rec_offset_sec
    placements = []  # (src_in_sec, src_out_sec, rec_in_sec)
    for s in segs:
        dur = s["out_sec"] - s["in_sec"]
        if s["kind"] == "block":
            placements.append({"src_in": s["in_sec"], "src_out": s["out_sec"], "rec_in": rec_pos_sec})
        rec_pos_sec += dur

    print(f"placements: {len(placements)}")

    # AppendToTimeline 用 batch 構築
    batch_tr1 = []
    batch_tr2 = []
    for p in placements:
        src_in_f = int(round(p["src_in"] * clip_fps))
        src_out_f = int(round(p["src_out"] * clip_fps))
        rec_f = int(round(p["rec_in"] * tl_fps))
        batch_tr1.append({
            "mediaPoolItem": tr1, "startFrame": src_in_f, "endFrame": src_out_f,
            "recordFrame": rec_f, "trackIndex": 1, "mediaType": 2,
        })
        batch_tr2.append({
            "mediaPoolItem": tr2, "startFrame": src_in_f, "endFrame": src_out_f,
            "recordFrame": rec_f, "trackIndex": 2, "mediaType": 2,
        })

    r1 = mp.AppendToTimeline(batch_tr1)
    print(f"Tr1 appended: {len(r1) if r1 else 0}")
    r2 = mp.AppendToTimeline(batch_tr2)
    print(f"Tr2 appended: {len(r2) if r2 else 0}")
    print("DONE")


main()
