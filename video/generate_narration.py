import asyncio
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
AUDIO.mkdir(parents=True, exist_ok=True)
FFMPEG = os.environ.get(
    "FFMPEG",
    r"C:\Users\student\AppData\Local\Temp\ffmpeg-dl\extracted\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe",
)
FFPROBE = os.environ.get(
    "FFPROBE",
    r"C:\Users\student\AppData\Local\Temp\ffmpeg-dl\extracted\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe",
)
VOICE = "ru-RU-SvetlanaNeural"
RATE = os.environ.get("VIDEO_RATE", "+30%")
LEAD = 1.4
GAP = 0.45
TAIL = 3.5
SR = 48000

SEGMENTS = [
    {
        "id": "seg01",
        "text": "Двадцать третьего июня тысяча девятьсот двенадцатого года в Лондоне родился Алан Тьюринг. Математик, логик и криптоаналитик, который задолго до первых компьютеров описал универсальную машину — устройство, способное вычислить любой алгоритм. Его идеи стали фундаментом искусственного интеллекта."
    },
    {
        "id": "seg02",
        "text": "Тьюринг учился в Кингс-колледже Кембриджа, а затем в Принстоне. В 1936 году он опубликовал работу о вычислимых числах. В ней появилась универсальная машина Тьюринга — абстрактное устройство, которое может выполнить любой алгоритм."
    },
    {
        "id": "seg03",
        "text": "Представьте машину с бесконечной лентой, которая читает символы и меняет их по правилам. Это и есть алгоритм. Одна такая машина может имитировать любую другую. Так родилась идея программы — и понимание того, что вычисление можно отделить от конкретного устройства."
    },
    {
        "id": "seg04",
        "text": "В 1939 году Тьюринг пришёл в Блетчли-парк — секретный центр британской разведки. Там он занялся немецкой шифровальной машиной «Энигма». Вместе с коллегами он создал «Бомбу» — устройство, которое перебирало возможные настройки шифра. Его работа давала союзникам жизненно важную информацию и, по оценкам историков, приблизила победу."
    },
    {
        "id": "seg05",
        "text": "После войны Тьюринг проектировал компьютеры: сначала Эй-Си-И, затем работал в Манчестере. В 1948 году он написал отчёт «Интеллиджент машинэри», где предложил сети простых элементов и идею машины, которую нужно не программировать целиком, а обучать. Это было предвидение нейросетей."
    },
    {
        "id": "seg06",
        "text": "В 1950 году в журнале «Майнд» вышла статья «Computing Machinery and Intelligence». Тьюринг заменил философский вопрос «может ли машина думать?» на эксперимент. Судья общается с человеком и машиной только текстом. Если он не может отличить машину от человека, она прошла тест Тьюринга. Тьюринг предполагал, что к двухтысячному году машины смогут обманывать судью в тридцати процентах случаев."
    },
    {
        "id": "seg07",
        "text": "В 1952 году он опубликовал работу о морфогенезе — математическую модель биологических узоров. В том же году его судили за гомосексуальность. Тьюринг потерял допуск к секретным работам. Седьмого июня 1954 года он умер в возрасте сорока одного года."
    },
    {
        "id": "seg08",
        "text": "Сегодня его имя носят премия Тьюринга, королевское помилование и банкнота в пятьдесят фунтов. Он не увидел цифровую эпоху, но именно его вопрос — может ли машина думать — до сих пор определяет границы искусственного интеллекта."
    },
]


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr[-2000:]}")
    return result.stdout.strip()


def probe_duration(path):
    out = run(
        [
            FFPROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(out)


def decode_to_wav(src, dst):
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(src),
            "-ar",
            str(SR),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )


def read_wav(path):
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 2
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == SR
        return handle.readframes(handle.getnframes())


def write_silence(frames):
    return b"\x00\x00\x00\x00" * frames


async def synth(text, out_path):
    last_error = None
    for attempt in range(1, 6):
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
            await communicate.save(str(out_path))
            if out_path.exists() and out_path.stat().st_size > 1000:
                print(f"  {out_path.name}: {out_path.stat().st_size} bytes")
                return
            raise RuntimeError("empty audio")
        except Exception as error:  # noqa: BLE001
            last_error = error
            print(f"  attempt {attempt} failed: {error}")
            await asyncio.sleep(1.5 * attempt)
    raise RuntimeError(f"TTS failed after retries: {last_error}")


async def main():
    print(f"Voice: {VOICE}; rate: {RATE}")
    for segment in SEGMENTS:
        mp3 = AUDIO / f"{segment['id']}.mp3"
        wav = AUDIO / f"{segment['id']}.wav"
        if not mp3.exists() or mp3.stat().st_size < 1000:
            print(f"Synthesizing {segment['id']} ...")
            await synth(segment["text"], mp3)
        if not wav.exists() or wav.stat().st_mtime < mp3.stat().st_mtime:
            decode_to_wav(mp3, wav)
        segment["duration"] = probe_duration(mp3)
        print(f"{segment['id']}: {segment['duration']:.2f}s")

    timeline = []
    cursor = LEAD
    chunks = [write_silence(int(LEAD * SR))]
    for segment in SEGMENTS:
        wav_path = AUDIO / f"{segment['id']}.wav"
        duration = probe_duration(wav_path)
        start = cursor
        end = start + duration
        timeline.append(
            {
                "id": segment["id"],
                "text": segment["text"],
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
            }
        )
        chunks.append(read_wav(wav_path))
        chunks.append(write_silence(int(GAP * SR)))
        cursor = end + GAP

    chunks.append(write_silence(int(TAIL * SR)))
    total = cursor + TAIL
    narration = ROOT / "narration.wav"
    with wave.open(str(narration), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        for chunk in chunks:
            handle.writeframes(chunk)

    data = {
        "voice": VOICE,
        "rate": RATE,
        "lead": LEAD,
        "gap": GAP,
        "tail": TAIL,
        "narration_end": round(timeline[-1]["end"], 3),
        "planned_total": round(total, 3),
        "segments": timeline,
    }
    (ROOT / "timings.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Narration end: {timeline[-1]['end']:.2f}s; planned total: {total:.2f}s")
    print(f"Wrote {narration}")


if __name__ == "__main__":
    asyncio.run(main())
