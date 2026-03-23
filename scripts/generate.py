#!/usr/bin/env python3
"""
podcast/scripts/generate.py — Podcast generation pipeline

Usage:
  python generate.py validate plan.json
  python generate.py generate --plan plan.json --name "episode_name"
  python generate.py generate --plan plan.json --name "episode_name" --skip-music
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILLS_DIR = os.environ.get("PIKABOT_SKILLS_DIR", "/app/skills")
WORKSPACE = os.environ.get("PIKABOT_WORKSPACE", "/data/.pikabot/workspace")

# Words per minute estimates for validation
CHARS_PER_MIN = {
    "zh": 200,
    "en": 780,  # ~130 words, ~6 chars/word
    "ja": 200,
    "ko": 180,
    "default": 200,
}


# ─────────────────────────────────────────────
# Plan loading
# ─────────────────────────────────────────────

def load_plan(plan_path: str) -> dict:
    with open(plan_path) as f:
        plan = json.load(f)

    # Load script from file if script_file is used
    if "script_file" in plan and "script" not in plan:
        script_path = plan["script_file"]
        if not os.path.isabs(script_path):
            script_path = os.path.join(WORKSPACE, script_path)
        with open(script_path) as f:
            plan["script"] = f.read().strip()

    return plan


# ─────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────

def validate(plan: dict) -> list[str]:
    errors = []
    warnings = []

    # Required fields
    for field in ["topic", "thesis", "duration_minutes", "language"]:
        if field not in plan:
            errors.append(f"Missing required field: {field}")

    if "persona" not in plan:
        errors.append("Missing required field: persona")
    else:
        if "voice_id_file" not in plan["persona"] and "voice_id" not in plan["persona"]:
            errors.append("persona must have voice_id_file or voice_id")

    if "script" not in plan:
        errors.append("Missing script (or script_file must resolve to script)")

    if errors:
        return errors, warnings

    # Script length vs duration
    script = plan["script"]
    lang = plan.get("language", "default")
    cpm = CHARS_PER_MIN.get(lang, CHARS_PER_MIN["default"])
    target_chars = plan["duration_minutes"] * cpm
    actual_chars = len(script)
    ratio = actual_chars / target_chars

    if ratio < 0.6:
        warnings.append(
            f"Script may be too short: {actual_chars} chars for {plan['duration_minutes']} min "
            f"(expected ~{int(target_chars)}). Estimated duration: {actual_chars/cpm:.1f} min."
        )
    elif ratio > 1.5:
        warnings.append(
            f"Script may be too long: {actual_chars} chars for {plan['duration_minutes']} min "
            f"(expected ~{int(target_chars)}). Estimated duration: {actual_chars/cpm:.1f} min."
        )
    else:
        print(f"  ✓ Script length OK: {actual_chars} chars → estimated {actual_chars/cpm:.1f} min "
              f"(target: {plan['duration_minutes']} min)")

    # Music validation
    if "music" in plan:
        m = plan["music"]
        if "style" not in m:
            errors.append("music.style is required when music is specified")
        vol = m.get("volume", 0.15)
        if vol > 0.35:
            warnings.append(f"music.volume {vol} is very high — may compete with voice. Recommend ≤0.25")

    # Persona
    persona = plan.get("persona", {})
    speed = persona.get("speed", 1.0)
    if speed > 1.5 or speed < 0.5:
        warnings.append(f"persona.speed {speed} is outside normal range (0.5–1.5)")

    return errors, warnings


# ─────────────────────────────────────────────
# Plan hash (for idempotent output filenames)
# ─────────────────────────────────────────────

def plan_hash(plan: dict) -> str:
    content = json.dumps({
        "script": plan.get("script", ""),
        "persona": plan.get("persona", {}),
        "music": plan.get("music", {}),
        "language": plan.get("language", ""),
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:8]


# ─────────────────────────────────────────────
# TTS
# ─────────────────────────────────────────────

def generate_tts(plan: dict, output_path: str) -> str:
    persona = plan["persona"]

    # Resolve voice ID
    voice_id_file = persona.get("voice_id_file")
    voice_id = persona.get("voice_id")

    if voice_id_file:
        if not os.path.isabs(voice_id_file):
            voice_id_file = os.path.join(WORKSPACE, voice_id_file)
        if not os.path.exists(voice_id_file):
            raise FileNotFoundError(f"Voice ID file not found: {voice_id_file}")
        voice_arg = voice_id_file
    elif voice_id:
        voice_arg = voice_id
    else:
        raise ValueError("No voice_id or voice_id_file in persona")

    script = plan["script"]
    lang = plan.get("language", "zh")
    speed = persona.get("speed", 1.0)
    pitch = persona.get("pitch", 0)
    vol = persona.get("vol", 1.0)

    tts_script = os.path.join(SKILLS_DIR, "minimax-voice/scripts/tts-minimax.py")

    cmd = [
        "python", tts_script,
        voice_arg,
        script,
        output_path,
        "--speed", str(speed),
        "--pitch", str(int(pitch)),
        "--vol", str(vol),
        "--language", lang,
    ]

    print(f"  → Generating TTS ({len(script)} chars, speed={speed}, pitch={pitch})...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"TTS failed:\n{result.stderr}")
    print(f"  ✓ TTS complete: {output_path}")
    return output_path


# ─────────────────────────────────────────────
# Music
# ─────────────────────────────────────────────

def generate_music(plan: dict, output_path: str) -> str:
    music = plan["music"]
    style = music["style"]
    lyrics = music.get("lyrics", "[intro]\nMm...\n[outro]\nMm...")

    music_script = os.path.join(SKILLS_DIR, "minimax-music/scripts/generate-music.py")

    cmd = ["python", music_script, style, lyrics, output_path]

    print(f"  → Generating background music (this takes 60–120s)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Music generation failed:\n{result.stderr}")
    print(f"  ✓ Music complete: {output_path}")
    return output_path


# ─────────────────────────────────────────────
# Mix
# ─────────────────────────────────────────────

def mix_audio(voice_path: str, bgm_path: str, output_path: str,
              bgm_volume: float = 0.15, fade_out_seconds: int = 5) -> str:
    # Get voice duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", voice_path],
        capture_output=True, text=True
    )
    voice_duration = float(result.stdout.strip())

    fade_start = max(0, voice_duration - fade_out_seconds)

    filter_complex = (
        f"[1:a]volume={bgm_volume},"
        f"afade=t=out:st={fade_start:.1f}:d={fade_out_seconds}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=3[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-codec:a", "libmp3lame", "-b:a", "192k",
        output_path
    ]

    print(f"  → Mixing audio (voice: {voice_duration:.1f}s, bgm vol: {bgm_volume})...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Mix failed:\n{result.stderr}")
    print(f"  ✓ Mix complete: {output_path}")
    return output_path


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run_generate(plan: dict, name: str, skip_music: bool = False,
                 output_dir: str = None) -> str:
    if output_dir is None:
        output_dir = os.path.join(WORKSPACE, "generated/podcast")
    os.makedirs(output_dir, exist_ok=True)

    h = plan_hash(plan)
    output_filename = f"{name}_{h}.mp3"
    output_path = os.path.join(output_dir, output_filename)

    if os.path.exists(output_path):
        print(f"  → Cached output exists: {output_path}")
        print(f"AUDIO:{output_path}")
        return output_path

    with tempfile.TemporaryDirectory() as tmpdir:
        voice_path = os.path.join(tmpdir, "voice.mp3")
        bgm_path = os.path.join(tmpdir, "bgm.mp3")

        has_music = "music" in plan and not skip_music

        # Step 1: TTS
        print("\n[1/3] TTS generation")
        generate_tts(plan, voice_path)

        if has_music:
            # Step 2: Music
            print("\n[2/3] Background music generation")
            generate_music(plan, bgm_path)

            # Step 3: Mix
            print("\n[3/3] Mixing")
            music = plan["music"]
            mix_audio(
                voice_path, bgm_path, output_path,
                bgm_volume=music.get("volume", 0.15),
                fade_out_seconds=music.get("fade_out_seconds", 5)
            )
        else:
            # No music — just copy voice
            print("\n[2/3] No music specified — voice only")
            import shutil
            shutil.copy(voice_path, output_path)
            print(f"\n[3/3] Output: {output_path}")

    print(f"\n✓ Done: {output_path}")
    print(f"AUDIO:{output_path}")
    return output_path


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Podcast generation pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # validate
    val_parser = subparsers.add_parser("validate", help="Validate a plan JSON")
    val_parser.add_argument("plan", help="Path to plan JSON")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate a podcast episode")
    gen_parser.add_argument("--plan", required=True, help="Path to plan JSON")
    gen_parser.add_argument("--name", required=True, help="Episode name (used in output filename)")
    gen_parser.add_argument("--skip-music", action="store_true", help="Skip music generation")
    gen_parser.add_argument("-o", "--output-dir", help="Output directory (default: generated/podcast/)")

    args = parser.parse_args()

    if args.command == "validate":
        plan = load_plan(args.plan)
        errors, warnings = validate(plan)
        if warnings:
            print("Warnings:")
            for w in warnings:
                print(f"  ⚠️  {w}")
        if errors:
            print("Errors:")
            for e in errors:
                print(f"  ✗ {e}")
            sys.exit(1)
        else:
            print("✓ Plan is valid")

    elif args.command == "generate":
        plan = load_plan(args.plan)
        errors, warnings = validate(plan)
        if warnings:
            for w in warnings:
                print(f"⚠️  {w}")
        if errors:
            print("Plan has errors — fix before generating:")
            for e in errors:
                print(f"  ✗ {e}")
            sys.exit(1)
        run_generate(
            plan,
            name=args.name,
            skip_music=args.skip_music,
            output_dir=args.output_dir,
        )

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
