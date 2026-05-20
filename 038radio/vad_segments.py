#!/usr/bin/env python3
"""
ピンマイク優位差分VAD: 2本のピンマイクから「自分の発話」セグメントを抽出。

自マイク(Tr1)が相手マイク(Tr2)より一定dB大きく、かつ無音閾値を超えるフレームが
連続する区間を発話セグメントとして抽出する。
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

BASE = Path(__file__).parent
WAV_DIR = BASE / "wav"

# ===== エピソード固有設定 =====
WAV_TR1 = "260420_001_Tr1.WAV"  # ★038で書き換え（千葉ピンマイク）
WAV_TR2 = "260420_001_Tr2.WAV"  # ★038で書き換え（東島ピンマイク）
# ===== VADパラメータ（基本変更不要）=====
FRAME_SEC = 0.1
MIN_SEG_SEC = 1.5
MAX_SEG_SEC = 20.0
MERGE_GAP_SEC = 1.0
RMS_FLOOR = 0.003
DOMINANCE_DB = 6.0  # 自マイクが相手より6dB以上大きい時だけ確実発話
# ===============================


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-10))


def frame_rms(wav: np.ndarray, sr: int, frame_sec: float) -> np.ndarray:
    frame_len = int(sr * frame_sec)
    n_frames = len(wav) // frame_len
    wav = wav[: n_frames * frame_len].reshape(n_frames, frame_len)
    return np.sqrt(np.mean(wav.astype(np.float32) ** 2, axis=1))


def detect_segments(rms_self, rms_other) -> list[tuple[float, float]]:
    self_dom = (db(rms_self) - db(rms_other)) > DOMINANCE_DB
    self_loud = rms_self > RMS_FLOOR
    speech = self_dom & self_loud

    segs = []
    i = 0
    n = len(speech)
    while i < n:
        if speech[i]:
            start = i
            while i < n and speech[i]:
                i += 1
            segs.append((start * FRAME_SEC, i * FRAME_SEC))
        else:
            i += 1

    merged = []
    for s, e in segs:
        if merged and s - merged[-1][1] < MERGE_GAP_SEC:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    filtered = [(s, e) for s, e in merged if e - s >= MIN_SEG_SEC]

    # 長すぎるセグメントを MAX_SEG_SEC で分割
    split = []
    for s, e in filtered:
        dur = e - s
        if dur <= MAX_SEG_SEC:
            split.append((s, e))
            continue
        n_chunks = int(np.ceil(dur / MAX_SEG_SEC))
        chunk_dur = dur / n_chunks
        for i in range(n_chunks):
            cs = s + i * chunk_dur
            ce = s + (i + 1) * chunk_dur if i < n_chunks - 1 else e
            split.append((cs, ce))
    return split


def ensure_16k(src_name: str, dst_name: str):
    """48kHz/24bit原本 → 16kHz/16bit mono 変換（既にあればスキップ）"""
    src = WAV_DIR / src_name
    dst = WAV_DIR / dst_name
    if dst.exists():
        return dst
    if not src.exists():
        raise FileNotFoundError(f"source WAV not found: {src}")
    print(f"Downsampling {src.name} → {dst.name}")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src),
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )
    return dst


def main():
    tr1_16k = ensure_16k(WAV_TR1, "Tr1_16k.wav")
    tr2_16k = ensure_16k(WAV_TR2, "Tr2_16k.wav")
    print("Loading WAVs...")
    tr1, sr1 = sf.read(tr1_16k, dtype="float32")
    tr2, sr2 = sf.read(tr2_16k, dtype="float32")
    assert sr1 == sr2 == 16000
    n = min(len(tr1), len(tr2))
    tr1, tr2 = tr1[:n], tr2[:n]

    print(f"Duration: {n/sr1:.1f}s")
    print("Computing RMS...")
    rms1 = frame_rms(tr1, sr1, FRAME_SEC)
    rms2 = frame_rms(tr2, sr2, FRAME_SEC)

    print("Detecting segments (Tr1=千葉)...")
    segs_chiba = detect_segments(rms1, rms2)
    print(f"  千葉 segments: {len(segs_chiba)}")
    print(f"  total speech: {sum(e-s for s,e in segs_chiba):.1f}s")

    print("Detecting segments (Tr2=東島)...")
    segs_tojima = detect_segments(rms2, rms1)
    print(f"  東島 segments: {len(segs_tojima)}")
    print(f"  total speech: {sum(e-s for s,e in segs_tojima):.1f}s")

    out = {
        "千葉": segs_chiba,
        "東島": segs_tojima,
    }
    out_path = BASE / "vad_segments.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n→ {out_path.name}")

    # 先頭10セグメントずつサンプル表示
    for name, segs in out.items():
        print(f"\n{name} 先頭10セグメント:")
        for s, e in segs[:10]:
            print(f"  {s:7.2f} - {e:7.2f}  ({e-s:.2f}s)")


if __name__ == "__main__":
    main()
