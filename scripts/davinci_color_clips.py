#!/usr/bin/env python3
"""
DaVinci Resolve Console Script: Color clips sequentially
タイムライン上のクリップに順番に色を付ける

Usage (DaVinci Console):
    exec(open('/path/to/davinci_color_clips.py').read())
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


def color_timeline_clips():
    """タイムラインの全クリップに順番に色を付ける"""

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

    # ビデオトラック数を取得
    track_count = timeline.GetTrackCount("video")
    print(f"ビデオトラック数: {track_count}")

    # 全クリップを収集（開始位置でソート用）
    all_clips = []

    for track_idx in range(1, track_count + 1):
        clips = timeline.GetItemListInTrack("video", track_idx)
        if clips:
            for clip in clips:
                start_frame = clip.GetStart()
                all_clips.append({
                    "clip": clip,
                    "track": track_idx,
                    "start": start_frame,
                    "name": clip.GetName(),
                })

    # 開始位置でソート
    all_clips.sort(key=lambda x: (x["start"], x["track"]))

    print(f"クリップ数: {len(all_clips)}")

    # 順番に色を付ける
    color_index = 0
    for i, item in enumerate(all_clips):
        clip = item["clip"]
        color = COLORS[color_index % len(COLORS)]

        # クリップに色を設定
        clip.SetClipColor(color)

        print(f"  {i+1}: {item['name']} → {color}")
        color_index += 1

    print(f"\n完了: {len(all_clips)}個のクリップに色を付けました")


# 実行
if __name__ == "__main__":
    color_timeline_clips()
else:
    # DaVinciコンソールから実行時
    color_timeline_clips()
