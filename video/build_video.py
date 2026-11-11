from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
CLIPS = BUILD / "clips"
CLIPS.mkdir(parents=True, exist_ok=True)
FFMPEG = os.environ.get(
    "FFMPEG",
    r"C:\Users\student\AppData\Local\Temp\ffmpeg-dl\extracted\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe",
)
FFPROBE = os.environ.get(
    "FFPROBE",
    r"C:\Users\student\AppData\Local\Temp\ffmpeg-dl\extracted\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe",
)

FPS = 30
TOTAL_SECONDS = 180.0
TOTAL_FRAMES = int(round(TOTAL_SECONDS * FPS))
SR = 48000


def run(cmd, description=""):
    print(f"\n>>> {description or ' '.join(cmd[:4])}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-5000:])
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def probe_duration(path):
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def fmt_srt_time(seconds):
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt_chunks(text, max_chars=95):
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        # Split long sentences at natural punctuation.
        parts = re.split(r"(?<=[,—;:])\s+", sentence)
        current = ""
        for part in parts:
            if len(current) + len(part) + 1 <= max_chars or not current:
                current = f"{current} {part}".strip()
            else:
                chunks.append(current)
                current = part
        if current:
            chunks.append(current)
    return chunks


def make_srt(timings):
    cues = []
    for segment in timings["segments"]:
        chunks = srt_chunks(segment["text"])
        total_chars = sum(len(chunk) for chunk in chunks) or 1
        cursor = segment["start"]
        for chunk in chunks:
            duration = (segment["end"] - segment["start"]) * (len(chunk) / total_chars)
            start = cursor
            end = min(segment["end"], start + duration)
            cues.append((start, end, chunk))
            cursor = end
    lines = []
    for i, (start, end, text) in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{fmt_srt_time(start)} --> {fmt_srt_time(end)}")
        lines.append(text)
        lines.append("")
    path = ROOT / "subtitles.srt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def scene_timeline(scenes, timings):
    segments = {segment["id"]: segment for segment in timings["segments"]}
    ids = [segment["id"] for segment in timings["segments"]]
    next_start = {}
    for i, sid in enumerate(ids[:-1]):
        next_start[sid] = segments[ids[i + 1]]["start"]

    result = []
    for scene in scenes:
        segment_id = scene["segment"]
        if segment_id == "tail":
            start = timings["narration_end"]
            end = TOTAL_SECONDS
        else:
            segment = segments[segment_id]
            start = segment["start"]
            end = next_start.get(segment_id, timings["narration_end"])
        result.append({**scene, "start": start, "end": end, "weight": float(scene["weight"])})

    # Compute durations within each block.
    for block_id in [*ids, "tail"]:
        block_scenes = [item for item in result if item["segment"] == block_id]
        if not block_scenes:
            continue
        block_start = block_scenes[0]["start"]
        block_end = block_scenes[0]["end"]
        available = block_end - block_start
        weight_sum = sum(item["weight"] for item in block_scenes)
        cursor = block_start
        for i, item in enumerate(block_scenes):
            if i == len(block_scenes) - 1:
                duration = block_end - cursor
            else:
                duration = available * item["weight"] / weight_sum
            item["start"] = cursor
            item["end"] = cursor + duration
            cursor += duration

    # Frame-align durations.
    frame_cursor = 0
    for item in result:
        frames = max(1, int(round((item["end"] - item["start"]) * FPS)))
        item["frames"] = frames
        item["start_frame"] = frame_cursor
        frame_cursor += frames
    # Trim or extend the final scene so the film is exactly 180 seconds.
    difference = TOTAL_FRAMES - frame_cursor
    result[-1]["frames"] += difference
    if result[-1]["frames"] < 1:
        raise RuntimeError("Final scene became too short")

    cursor = 0
    for item in result:
        item["start"] = cursor / FPS
        item["end"] = (cursor + item["frames"]) / FPS
        item["duration"] = item["frames"] / FPS
        cursor += item["frames"]
    return result


def render_clip(scene, index):
    out = CLIPS / f"{index:02d}_{scene['id']}.mp4"
    if out.exists() and os.environ.get("REBUILD_CLIPS") != "1":
        return out

    frames = scene["frames"]
    duration = frames / FPS
    fade = 0.32
    # Alternate gentle push-in and pull-out so adjacent scenes feel different.
    if index % 3 == 0:
        zoom = "min(1.06,1.01+0.00007*on)"
        x = "iw/2-(iw/zoom/2)+sin(on/120)*7"
        y = "ih/2-(ih/zoom/2)+cos(on/160)*5"
    elif index % 3 == 1:
        zoom = "max(1.0,1.07-0.00007*on)"
        x = "iw/2-(iw/zoom/2)+sin(on/180)*10"
        y = "ih/2-(ih/zoom/2)"
    else:
        zoom = "min(1.055,1.01+0.00006*on)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)+sin(on/150)*7"

    vf = (
        "scale=3072:1728,"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s=1920x1080:fps={FPS},"
        "eq=contrast=1.025:saturation=1.04,"
        f"fade=t=in:st=0:d={fade},"
        f"fade=t=out:st={max(0, duration - fade):.3f}:d={fade},"
        "format=yuv420p"
    )
    cmd = [
        FFMPEG,
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(FPS),
        "-i",
        scene["file"],
        "-vf",
        vf,
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-r",
        str(FPS),
        "-g",
        "60",
        "-keyint_min",
        "60",
        "-sc_threshold",
        "0",
        str(out),
    ]
    run(cmd, f"Render {scene['id']} ({duration:.2f}s)")
    return out


def make_music(total=TOTAL_SECONDS, path=BUILD / "music.wav"):
    n = int(total * SR)
    t = np.arange(n, dtype=np.float64) / SR

    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)

    # A-minor / F / C / G progression: dark, slow, cinematic.
    sections = [
        (0.0, 26.0, [110.00, 130.81, 164.81]),
        (24.0, 55.0, [87.31, 110.00, 130.81]),
        (53.0, 80.0, [130.81, 164.81, 196.00]),
        (78.0, 110.0, [98.00, 123.47, 146.83]),
        (108.0, 140.0, [110.00, 130.81, 164.81]),
        (138.0, 164.0, [87.31, 110.00, 130.81]),
        (162.0, 180.0, [110.00, 164.81, 220.00]),
    ]

    for start, end, notes in sections:
        start_i = max(0, int(start * SR))
        end_i = min(n, int(end * SR))
        local_t = t[start_i:end_i] - t[start_i]
        local_n = end_i - start_i
        attack = np.clip(local_t / 4.0, 0, 1)
        release = np.clip((local_n / SR - local_t) / 5.0, 0, 1)
        env = np.minimum(attack, release)
        env = env * env * (3 - 2 * env)
        for note in notes:
            for detune, phase, amp in [(0.997, 0.0, 0.34), (1.003, 0.9, 0.28), (2.0, 0.3, 0.09)]:
                f = note * detune
                vibrato = 0.16 * np.sin(2 * np.pi * 0.055 * local_t + phase)
                signal = np.sin(2 * np.pi * f * local_t + vibrato + phase)
                signal += 0.22 * np.sin(2 * np.pi * f * 2.003 * local_t + 0.4)
                left[start_i:end_i] += signal * env * amp
                right[start_i:end_i] += signal * env * amp * 0.96 + 0.025 * np.sin(2 * np.pi * f * 1.002 * local_t + 1.1) * env

    # Low drone, always present.
    drone_env = np.clip(t / 8.0, 0, 1) * np.clip((total - t) / 9.0, 0, 1)
    drone_env = drone_env * drone_env * (3 - 2 * drone_env)
    for f, amp in [(55.0, 0.10), (82.41, 0.05)]:
        left += np.sin(2 * np.pi * f * t + 0.2) * drone_env * amp
        right += np.sin(2 * np.pi * f * 1.003 * t + 1.4) * drone_env * amp

    # Subtle heartbeat pulse under the middle chapter.
    pulse_region = (t > 55) & (t < 150)
    for beat in np.arange(56.0, 150.0, 2.0):
        idx = int(beat * SR)
        length = int(0.45 * SR)
        if idx + length >= n:
            continue
        lt = np.arange(length) / SR
        thump = np.sin(2 * np.pi * 47 * lt) * np.exp(-lt * 10.0)
        fade_region = np.clip((t[idx] - 55) / 6.0, 0, 1) * np.clip((150 - t[idx]) / 6.0, 0, 1)
        left[idx:idx + length] += thump * 0.055 * fade_region
        right[idx:idx + length] += thump * 0.055 * fade_region

    # Gentle high air, deterministic and quiet.
    rng = np.random.default_rng(11)
    air = rng.normal(0, 1, n)
    # Smooth the noise with a long moving average using cumulative sums.
    window = 900
    csum = np.cumsum(np.insert(air, 0, 0.0))
    air = (csum[window:] - csum[:-window]) / window
    air = np.pad(air, (window // 2, n - len(air) - window // 2), mode="edge")
    air *= np.clip(t / 10.0, 0, 1) * np.clip((total - t) / 10.0, 0, 1)
    left += air * 0.055
    right += np.roll(air, 1800) * 0.05

    # Global fades.
    global_env = np.clip(t / 4.0, 0, 1) * np.clip((total - t) / 7.0, 0, 1)
    left *= global_env
    right *= global_env

    peak = max(np.abs(left).max(), np.abs(right).max(), 1e-9)
    left = left / peak * 0.72
    right = right / peak * 0.72
    stereo = np.stack([left, right], axis=1)
    pcm = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm.tobytes())

    print(f"Music: {path} ({total:.1f}s)")
    return path


def concat_clips(clips, path=BUILD / "silent.mp4"):
    list_path = BUILD / "concat.txt"
    list_path.write_text(
        "\n".join(f"file '{clip.as_posix()}'" for clip in clips) + "\n",
        encoding="utf-8",
    )
    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(path),
        ],
        "Concatenate scenes",
    )
    return path


def finish_video(silent, narration, music, subtitles, output):
    filter_complex = (
        "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[voice];"
        "[2:a]loudnorm=I=-30:TP=-6:LRA=8,aresample=48000[bed];"
        "[voice][bed]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
        "alimiter=limit=0.95[a]"
    )
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(silent),
            "-i",
            str(narration),
            "-i",
            str(music),
            "-i",
            str(subtitles),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-map",
            "3:s:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=rus",
            "-metadata:s:s:0",
            "title=Русские субтитры",
            "-metadata",
            "title=Алан Тьюринг: человек, который придумал ИИ",
            "-metadata",
            "artist=TURING.",
            "-metadata",
            "comment=Образовательный проект о Алане Тьюринге",
            "-t",
            str(TOTAL_SECONDS),
            "-movflags",
            "+faststart",
            str(output),
        ],
        "Mux video, narration, music and subtitles",
    )


def main():
    timings = json.loads((ROOT / "timings.json").read_text(encoding="utf-8"))
    scenes = json.loads((ROOT / "scenes.json").read_text(encoding="utf-8"))
    timeline = scene_timeline(scenes, timings)
    total_frames = sum(scene["frames"] for scene in timeline)
    print(f"Timeline: {len(timeline)} scenes, {total_frames} frames, {total_frames / FPS:.2f}s")
    for scene in timeline:
        print(f"  {scene['id']}: {scene['start']:.2f}–{scene['end']:.2f} ({scene['duration']:.2f}s)")

    srt = make_srt(timings)
    print(f"Subtitles: {srt}")

    music = make_music()
    clips = [render_clip(scene, i) for i, scene in enumerate(timeline)]
    silent = concat_clips(clips)
    final = ROOT / "turing-3min.mp4"
    finish_video(silent, ROOT / "narration.wav", music, srt, final)
    poster = ROOT / "poster.jpg"
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            "4",
            "-i",
            str(final),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(poster),
        ],
        "Make poster",
    )
    print(f"\nDone: {final}")
    print(f"Duration: {probe_duration(final):.3f}s")
    print(f"Size: {final.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
