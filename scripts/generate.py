#!/usr/bin/env python3
"""
Podcast generation script v2 — TTS-first pipeline with music library.

Pipeline:
  1. Split script by [MARKER] tags → named text segments
  2. Generate TTS per segment (with per-segment speed overrides)
  3. Measure actual TTS durations
  4. Compute music cue durations from measured TTS
  5. Generate music library (once per asset, reused across cues)
  6. Build timeline and mix with ffmpeg adelay+amix
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(os.environ.get("PIKABOT_WORKSPACE", "/data/.pikabot/workspace"))
SKILLS_DIR = Path(os.environ.get("PIKABOT_SKILLS_DIR", "/app/skills"))

MARKER_RE = re.compile(r'\[([A-Z][A-Z\s]+?)(?:\s*[—\-][^\]]+)?\]')


def log(msg):
    print(msg, flush=True)


# ─────────────────────────────────────────────────────────────
# 1. Script parsing
# ─────────────────────────────────────────────────────────────

def split_script_by_markers(script_text: str, music_cues: list) -> list:
    """
    Split script into alternating text and marker segments.
    Text segments get ids: seg_pre (first), seg_1, seg_2, ... seg_conclusion (last).
    Marker segments get ids matching their music_cue id.
    """
    # Build marker_keyword → cue_id map
    cue_by_keyword = {}
    for cue in music_cues:
        if "marker" in cue:
            m = MARKER_RE.match(cue["marker"])
            if m:
                cue_by_keyword[m.group(1).strip()] = cue["id"]

    segments = []
    text_idx = 0
    pos = 0

    for match in MARKER_RE.finditer(script_text):
        # Text before this marker
        text = script_text[pos:match.start()].strip()
        if text:
            if text_idx == 0:
                seg_id = "seg_pre"
            else:
                seg_id = f"seg_{text_idx}"
            segments.append({"id": seg_id, "type": "text", "text": text, "index": text_idx})
            text_idx += 1
        pos = match.end()

        # The marker
        keyword = match.group(1).strip()
        cue_id = cue_by_keyword.get(keyword, keyword.lower().replace(" ", "_"))
        segments.append({"id": cue_id, "type": "marker", "keyword": keyword})

    # Remaining text after last marker
    tail = script_text[pos:].strip()
    if tail:
        seg_id = "seg_conclusion"
        segments.append({"id": seg_id, "type": "text", "text": tail, "index": text_idx})

    return segments


# ─────────────────────────────────────────────────────────────
# 2. TTS generation
# ─────────────────────────────────────────────────────────────

def get_audio_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def read_voice_id(voice_id_file: str) -> str:
    return (WORKSPACE / voice_id_file).read_text().strip()


def run_tts(text: str, voice_id: str, speed: float, pitch: int, vol: float, out_path: str):
    tts_script = SKILLS_DIR / "minimax-voice" / "scripts" / "tts.py"
    cmd = [
        sys.executable, str(tts_script),
        "--voice-id", voice_id,
        "--text", text,
        "--speed", str(speed),
        "--pitch", str(pitch),
        "--vol", str(vol),
        "--output", out_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"TTS failed:\n{r.stderr}")


def generate_all_tts(segments: list, voice_cfg: dict, tmpdir: str) -> dict:
    """Returns {seg_id: {path, duration_s}}"""
    voice_id = read_voice_id(voice_cfg["voice_id_file"])
    base_speed = voice_cfg.get("base_speed", 0.92)
    pitch = voice_cfg.get("base_pitch", -1)
    vol = voice_cfg.get("base_vol", 1.0)
    overrides = voice_cfg.get("speed_overrides", {})

    results = {}
    for seg in segments:
        if seg["type"] != "text":
            continue
        sid = seg["id"]
        speed = overrides.get(sid, base_speed)
        out = os.path.join(tmpdir, f"tts_{sid}.mp3")
        log(f"  TTS [{sid}] speed={speed} ({len(seg['text'])} chars)...")
        run_tts(seg["text"], voice_id, speed, pitch, vol, out)
        dur = get_audio_duration(out)
        results[sid] = {"path": out, "duration_s": dur}
        log(f"    → {dur:.1f}s")

    return results


# ─────────────────────────────────────────────────────────────
# 3. Music duration computation
# ─────────────────────────────────────────────────────────────

def compute_music_durations(segments: list, tts: dict, music_cues: list) -> dict:
    """
    Returns {cue_id: required_duration_s}

    For duration_source="next_tts_segment":
      duration = voice_delay_s + tts_next_seg_duration + duration_buffer_s
      (music_delay reduces the effective preroll but not the total required duration)
    For type="silence": use duration_s directly.
    """
    # Map each marker cue_id → the next text segment id
    cue_to_next_seg = {}
    for i, seg in enumerate(segments):
        if seg["type"] == "marker":
            for j in range(i + 1, len(segments)):
                if segments[j]["type"] == "text":
                    cue_to_next_seg[seg["id"]] = segments[j]["id"]
                    break

    computed = {}
    for cue in music_cues:
        cid = cue["id"]
        if cue.get("type") == "silence":
            computed[cid] = float(cue["duration_s"])
            continue

        source = cue.get("duration_source", "fixed")
        if source == "next_tts_segment":
            next_sid = cue_to_next_seg.get(cid)
            if next_sid and next_sid in tts:
                tts_dur = tts[next_sid]["duration_s"]
                voice_delay = cue.get("voice_delay_s", 0)
                music_delay = cue.get("music_delay_s", 0)
                buffer = cue.get("duration_buffer_s", 2)
                # Music covers: lead-in (voice_delay - music_delay) + speech + buffer
                lead_in = max(0, voice_delay - music_delay)
                computed[cid] = lead_in + tts_dur + buffer
            else:
                computed[cid] = float(cue.get("duration_s", 30))
        else:
            computed[cid] = float(cue.get("duration_s", 30))

    return computed


# ─────────────────────────────────────────────────────────────
# 4. Music library generation
# ─────────────────────────────────────────────────────────────

def run_music_gen(style: str, lyrics: str, out_path: str):
    music_script = SKILLS_DIR / "minimax-music" / "scripts" / "generate.py"
    cmd = [
        sys.executable, str(music_script),
        "--prompt", style,
        "--lyrics", lyrics,
        "--output", out_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Music gen failed:\n{r.stderr}")


def prepare_library(music_library: dict, music_cues: list, cue_durations: dict, tmpdir: str) -> dict:
    """
    Compute max required duration per asset across all cues that reference it.
    Generate each asset once.
    Returns {asset_id: path}
    """
    asset_max = {}
    for cue in music_cues:
        if cue.get("type") == "silence":
            continue
        aid = cue.get("music")
        if aid:
            req = cue_durations.get(cue["id"], 30)
            asset_max[aid] = max(asset_max.get(aid, 0), req)

    files = {}
    for aid, cfg in music_library.items():
        max_dur = asset_max.get(aid, cfg.get("base_duration_s", 30))
        base_dur = cfg.get("base_duration_s", 30)
        log(f"  Music library [{aid}]: max needed={max_dur:.0f}s, base={base_dur}s")
        out = os.path.join(tmpdir, f"lib_{aid}.mp3")
        run_music_gen(cfg["style"], cfg.get("lyrics", "[intro]\nMm...\n[outro]\nMm..."), out)
        actual = get_audio_duration(out)
        log(f"    → {actual:.1f}s generated")
        files[aid] = out

    return files


# ─────────────────────────────────────────────────────────────
# 5. Timeline + ffmpeg mix
# ─────────────────────────────────────────────────────────────

def loop_or_trim(src: str, target_s: float, out: str):
    """Trim or loop src to exactly target_s seconds."""
    src_dur = get_audio_duration(src)
    if src_dur >= target_s:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-t", str(target_s), "-ar", "44100", out],
            check=True, capture_output=True
        )
    else:
        loops = int(target_s / src_dur) + 2
        subprocess.run(
            ["ffmpeg", "-y", "-stream_loop", str(loops), "-i", src,
             "-t", str(target_s), "-ar", "44100", out],
            check=True, capture_output=True
        )


def apply_fades(src: str, out: str, fade_in: float, fade_out: float, duration: float):
    filters = []
    if fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in}")
    if fade_out > 0:
        start = max(0, duration - fade_out)
        filters.append(f"afade=t=out:st={start}:d={fade_out}")
    if not filters:
        shutil.copy(src, out)
        return
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-af", ",".join(filters), out],
        check=True, capture_output=True
    )


def mix_all(segments, tts, lib_files, music_cues, cue_durations, mix_cfg, out_path, tmpdir):
    """
    Build voice + music event lists, then mix with ffmpeg adelay+amix.
    """
    cue_map = {c["id"]: c for c in music_cues}

    voice_events = []   # [{path, start_s, duration_s, vol}]
    music_events = []

    current_time = 0.0
    placed_tts = set()

    # Walk segments in order
    i = 0
    while i < len(segments):
        seg = segments[i]

        if seg["type"] == "text":
            sid = seg["id"]
            if sid in tts and sid not in placed_tts:
                info = tts[sid]
                voice_events.append({
                    "path": info["path"],
                    "start_s": current_time,
                    "duration_s": info["duration_s"],
                    "vol": 1.0
                })
                current_time += info["duration_s"]
                placed_tts.add(sid)

        elif seg["type"] == "marker":
            cid = seg["id"]
            cue = cue_map.get(cid)
            if not cue:
                i += 1
                continue

            cue_dur = cue_durations.get(cid, 0)

            if cue.get("type") == "silence":
                current_time += cue_dur
                i += 1
                continue

            voice_delay = cue.get("voice_delay_s", 0)
            music_delay = cue.get("music_delay_s", 0)
            aid = cue.get("music")

            # Absolute start times
            music_abs_start = current_time + music_delay
            voice_abs_start = current_time + voice_delay

            # Find and place next text segment
            next_text = None
            for j in range(i + 1, len(segments)):
                if segments[j]["type"] == "text":
                    next_text = segments[j]
                    break

            if next_text and next_text["id"] in tts and next_text["id"] not in placed_tts:
                info = tts[next_text["id"]]
                voice_events.append({
                    "path": info["path"],
                    "start_s": voice_abs_start,
                    "duration_s": info["duration_s"],
                    "vol": 1.0
                })
                placed_tts.add(next_text["id"])
                current_time = voice_abs_start + info["duration_s"]

            # Prepare and place music
            if aid and aid in lib_files:
                trimmed = os.path.join(tmpdir, f"cue_{cid}_trim.mp3")
                faded   = os.path.join(tmpdir, f"cue_{cid}_faded.mp3")
                loop_or_trim(lib_files[aid], cue_dur, trimmed)
                apply_fades(trimmed, faded,
                            cue.get("fade_in_s", 0),
                            cue.get("fade_out_s", 0),
                            cue_dur)
                music_events.append({
                    "path": faded,
                    "start_s": music_abs_start,
                    "duration_s": cue_dur,
                    "vol": cue.get("vol", 0.1)
                })

        i += 1

    total = max(
        max((e["start_s"] + e["duration_s"] for e in voice_events), default=0),
        max((e["start_s"] + e["duration_s"] for e in music_events), default=0)
    )
    log(f"  Timeline: {total:.1f}s | {len(voice_events)} voice + {len(music_events)} music events")

    # Build ffmpeg command
    all_events = [(e, "v") for e in voice_events] + [(e, "m") for e in music_events]
    input_args = []
    filter_parts = []
    labels = []

    for idx, (evt, kind) in enumerate(all_events):
        delay_ms = int(evt["start_s"] * 1000)
        vol = evt["vol"]
        input_args += ["-i", evt["path"]]
        lbl = f"s{idx}"
        filter_parts.append(
            f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={vol}[{lbl}]"
        )
        labels.append(f"[{lbl}]")

    n = len(labels)
    filter_parts.append(
        f"{''.join(labels)}amix=inputs={n}:duration=longest:normalize=0[out]"
    )

    cmd = ["ffmpeg", "-y"] + input_args + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-b:a", mix_cfg.get("output_bitrate", "192k"),
        out_path
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg mix failed:\n{r.stderr[-800:]}")

    return total


# ─────────────────────────────────────────────────────────────
# Main generation entry
# ─────────────────────────────────────────────────────────────

def generate(plan: dict, name: str, output_dir: Path) -> str:
    log(f"\n🎙  Podcast v2: {name}")
    log("=" * 52)

    script_text = (WORKSPACE / plan["script_file"]).read_text(encoding="utf-8")
    music_cues    = plan.get("music_cues", [])
    music_library = plan.get("music_library", {})
    voice_cfg     = plan.get("voice", {})
    mix_cfg       = plan.get("mix", {})

    with tempfile.TemporaryDirectory() as tmpdir:

        log("\n[1/4] Splitting script + generating TTS per segment...")
        segs = split_script_by_markers(script_text, music_cues)
        text_segs = [s for s in segs if s["type"] == "text"]
        mark_segs = [s for s in segs if s["type"] == "marker"]
        log(f"  {len(text_segs)} text segments, {len(mark_segs)} markers")
        tts = generate_all_tts(segs, voice_cfg, tmpdir)

        log("\n[2/4] Computing music durations from TTS measurements...")
        cue_durs = compute_music_durations(segs, tts, music_cues)
        for cid, dur in cue_durs.items():
            log(f"  {cid}: {dur:.1f}s")

        log("\n[3/4] Generating music library...")
        lib = prepare_library(music_library, music_cues, cue_durs, tmpdir)

        log("\n[4/4] Mixing timeline...")
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_hash = hashlib.md5(json.dumps(plan, sort_keys=True).encode()).hexdigest()[:8]
        out_path = str(output_dir / f"{name}_{plan_hash}.mp3")

        mix_all(segs, tts, lib, music_cues, cue_durs, mix_cfg, out_path, tmpdir)

    final_dur = get_audio_duration(out_path)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    log(f"\n✓ Output: {out_path}")
    log(f"  Duration: {final_dur:.1f}s ({final_dur/60:.1f} min) | {size_mb:.1f} MB")
    return out_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def cmd_generate(args):
    with open(args.plan) as f:
        plan = json.load(f)
    name = args.name or Path(args.plan).stem
    out = generate(plan, name, WORKSPACE / "generated" / "podcast")
    print(f"\nOutput: {out}")


def cmd_validate(args):
    with open(args.plan) as f:
        plan = json.load(f)
    errors = []
    if "voice" not in plan or "voice_id_file" not in plan.get("voice", {}):
        errors.append("Missing voice.voice_id_file")
    if "script_file" not in plan and "script" not in plan:
        errors.append("Missing script_file or script")
    if "music_library" not in plan:
        errors.append("Missing music_library")
    lib_keys = set(plan.get("music_library", {}).keys())
    for cue in plan.get("music_cues", []):
        if cue.get("type") == "silence":
            continue
        ref = cue.get("music")
        if ref and ref not in lib_keys:
            errors.append(f"Cue '{cue['id']}' references unknown music '{ref}'")
    if errors:
        print("✗ Validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"✓ Plan valid: {plan.get('meta', {}).get('topic', '?')} "
              f"({plan.get('meta', {}).get('duration_minutes', '?')} min)")
        print(f"  Library: {list(lib_keys)}")
        print(f"  Cues: {[c['id'] for c in plan.get('music_cues', [])]}")


def main():
    p = argparse.ArgumentParser(description="Podcast generation tool v2")
    sub = p.add_subparsers(dest="cmd")

    g = sub.add_parser("generate")
    g.add_argument("--plan", required=True)
    g.add_argument("--name")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate")
    v.add_argument("plan")
    v.set_defaults(func=cmd_validate)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
