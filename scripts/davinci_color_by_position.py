#!/usr/bin/env python3
"""
DaVinci Resolve Script: Color clips by start position
同一開始位置のクリップに同じ色を付ける（粗編用）

Usage:
    DaVinci Resolve → Workspace → Scripts から実行
    または Console: exec(open('/path/to/davinci_color_by_position.py').read())
"""

# DaVinci Resolve色リスト（16色）
COLORS = [
    "Orange",    # 1
    "Apricot",   # 2
    "Yellow",    # 3
    "Lime",      # 4
    "Olive",     # 5
    "Green",     # 6
    "Teal",      # 7
    "Navy",      # 8
    "Blue",      # 9
    "Purple",    # 10
    "Violet",    # 11
    "Pink",      # 12
    "Tan",       # 13
    "Beige",     # 14
    "Brown",     # 15
    "Chocolate", # 16
]


def color_clips_by_position():
    """同一開始位置のクリップに同じ色を付ける"""

    # DaVinci Resolve APIに接続
    resolve = app.GetResolve()
    if not resolve:
        print("Error: DaVinci Resolveに接続できません")
        return

    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        print("Error: プロジェクトが開かれていません")
        return

    timeline = project.GetCurrentTimeline()
    if not timeline:
        print("Error: タイムラインが選択されていません")
        return

    timeline_name = timeline.GetName()
    print(f"タイムライン: {timeline_name}")

    # 全トラック（ビデオ＋オーディオ）からクリップを収集
    clips_by_start = {}

    # ビデオトラック
    video_count = timeline.GetTrackCount("video")
    for t in range(1, video_count + 1):
        clips = timeline.GetItemListInTrack("video", t)
        if clips:
            for c in clips:
                start = c.GetStart()
                if start not in clips_by_start:
                    clips_by_start[start] = []
                clips_by_start[start].append({"clip": c, "type": "V", "track": t})

    # オーディオトラック
    audio_count = timeline.GetTrackCount("audio")
    for t in range(1, audio_count + 1):
        clips = timeline.GetItemListInTrack("audio", t)
        if clips:
            for c in clips:
                start = c.GetStart()
                if start not in clips_by_start:
                    clips_by_start[start] = []
                clips_by_start[start].append({"clip": c, "type": "A", "track": t})

    print(f"ビデオトラック: {video_count}, オーディオトラック: {audio_count}")
    print(f"グループ数: {len(clips_by_start)}")

    # 開始位置でソートしてグループごとに色付け
    sorted_starts = sorted(clips_by_start.keys())
    total_clips = 0

    for i, start in enumerate(sorted_starts):
        color = COLORS[i % len(COLORS)]
        group = clips_by_start[start]

        for item in group:
            item["clip"].SetClipColor(color)
            total_clips += 1

        # グループ情報を表示
        track_info = ", ".join([f"{item['type']}{item['track']}" for item in group])
        print(f"  {i+1}: frame {start} → {color} ({len(group)}クリップ: {track_info})")

    print(f"\n完了: {len(sorted_starts)}グループ, {total_clips}クリップに色を付けました")


# 実行
if __name__ == "__main__":
    color_clips_by_position()
else:
    # DaVinciコンソールから実行時
    color_clips_by_position()
