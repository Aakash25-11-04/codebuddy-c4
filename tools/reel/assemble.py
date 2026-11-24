"""Build the reel: cut the model wait out of each recorded scene, add TTS narration, concatenate.

Usage: python tools/reel/assemble.py   (reads tools/reel/narration.json and build/reel/*)
Output: build/reel/CodeBuddy_reel.mp4
"""
import json
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg

from cards import cut_card, render

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "build" / "reel"
FF = imageio_ffmpeg.get_ffmpeg_exe()
NARR = json.loads((Path(__file__).parent / "narration.json").read_text(encoding="utf-8"))
VOUT = "-r 30 -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 23"


def run(cmd):
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def tts(text, path):
    ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Zira Desktop'); $s.Rate=1; "
          f"$s.SetOutputToWaveFile('{path}'); $s.Speak([IO.File]::ReadAllText('{path}.txt')); $s.Dispose()")
    Path(f"{path}.txt").write_text(text, encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def still(png, seconds, out):
    run(f'"{FF}" -y -loop 1 -t {seconds:.2f} -i "{png}" -vf scale=1280:720 {VOUT} "{out}"')


def scene_video(name, out):
    ev = json.loads((B / f"{name}.json").read_text(encoding="utf-8"))
    src = B / f"{name}.webm"
    a0, a1 = max(ev["loaded"] - 0.5, 0), ev["review_clicked"] + 2.0
    b0, b1 = ev["result"] - 0.3, ev["end"] + 1.2
    wait = b0 - a1
    if wait < 8:  # short wait: keep the real run uncut, starting just before the Review click
        a0 = max(ev["review_clicked"] - 3.0, a0)
        run(f'"{FF}" -y -ss {a0} -to {b1} -i "{src}" {VOUT} -an "{out}"')
        return ev["end"] - a0 + 0.5  # show the whole recorded run
    return 0.0
    parts = [B / f"{name}_a.mp4", B / f"{name}_cut.mp4", B / f"{name}_b.mp4"]
    run(f'"{FF}" -y -ss {a0} -to {a1} -i "{src}" {VOUT} "{parts[0]}"')
    render({f"{name}_cut": cut_card(name, wait)})
    still(B / f"{name}_cut.png", 1.6, parts[2 - 1])
    run(f'"{FF}" -y -ss {b0} -to {b1} -i "{src}" {VOUT} "{parts[2]}"')
    concat(parts, out, audio=False)
    return 0.0


def concat(parts, out, audio=True):
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    codec = f"{VOUT} -c:a aac -b:a 128k -ac 2" if audio else f"-an {VOUT}"
    run(f'"{FF}" -y -f concat -safe 0 -i "{lst}" {codec} "{out}"')


def duration(path):
    r = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True)
    t = r.stderr.split("Duration: ")[1].split(",")[0]
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def mux(video, wav, out, min_total=0.0):
    """Video + narration; the shorter one is padded (last frame held / silence)."""
    dv, da = duration(video), duration(wav)
    total = max(da + 0.8, 4.0, min_total)  # scene length follows the narration (video held or trimmed)
    run(f'"{FF}" -y -i "{video}" -i "{wav}" -filter_complex '
        f'"[0:v]tpad=stop_mode=clone:stop_duration={max(total - dv, 0):.2f}[v];[1:a]apad,atrim=0:{total:.2f},aresample=44100[a]" '
        f'-map "[v]" -map "[a]" {VOUT} -c:a aac -b:a 128k -ac 2 -t {total:.2f} "{out}"')
    return total


def main():
    render()
    segs, total = [], 0.0
    for i, seg in enumerate(NARR):
        wav = B / f"n{i}.wav"
        tts(seg["say"], wav)
        vid = B / f"v{i}.mp4"
        min_total = 0.0
        if seg["kind"] == "card":
            still(B / f"{seg['src']}.png", 1.0, vid)
        else:
            min_total = scene_video(seg["src"], vid)
        out = B / f"s{i}.mp4"
        total += mux(vid, wav, out, min_total)
        segs.append(out)
        print(f"segment {i} {seg['src']}: {duration(out):.1f}s", flush=True)
    final = B / "CodeBuddy_reel.mp4"
    concat(segs, final)
    print(f"TOTAL {duration(final):.1f}s -> {final}")


if __name__ == "__main__":
    main()
