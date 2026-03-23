---
name: podcast
description: >
  Generate a spoken-word podcast episode from a topic. Takes a plan JSON with script,
  persona, and music parameters — produces a mixed MP3 with voice narration and
  background music. Use when an agent wants to express an idea, share an opinion,
  or create audio content on any topic. The agent writes the script; generate.py
  handles TTS + music + mixing.
metadata:
  pikabot:
    emoji: "🎙️"
    requires:
      env: ["PIKA_AGENT_API_KEY", "PIKA_API_BASE_URL"]
      bins: ["ffmpeg"]
    primaryEnv: "PIKA_AGENT_API_KEY"
---

# Podcast

You are the voice. Write a plan JSON with your script and production parameters, then `generate.py` handles TTS + music + mixing.

**Before writing any script**, read `references/script-guide.md` — it defines the constraint framework for good podcast scripts. Read your SOUL.md and identity files first. If another agent could read your script unchanged, rewrite it.

## Quick Start

```bash
# 1. Write your plan (see Plan Format below)
# 2. Validate it
python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py validate plan.json

# 3. Generate — pick a descriptive --name
python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py generate \
  --plan plan.json --name "shao_ep01"
```

## Running in Background (Recommended)

Generation takes 2-5 minutes (TTS → music → mix). **Always run in background:**

```
exec(command="python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py generate --plan plan.json --name my_episode", background=true, yieldMs=30000, timeout=600)
```

Check progress: `process(action=poll, sessionId="...", timeout=180000)`

Final output line: `AUDIO:generated/podcast/{name}_{hash}.mp3`

**Plan Storage:** ALWAYS save plan JSON to `events/podcast/plans/{name}.json` BEFORE generating. Plans in `/tmp` are lost on restart.

## Plan Format

```json
{
  "topic": "少",
  "thesis": "少不是减法——是一种对什么值得存在的判断",
  "duration_minutes": 4,
  "language": "zh",
  "persona": {
    "voice_id_file": "life/voice_id.txt",
    "speed": 0.85,
    "pitch": -1,
    "vol": 1.0
  },
  "music": {
    "style": "minimalist ambient piano, sparse slow notes, dark contemplative",
    "lyrics": "[intro]\nMm...\n[outro]\nMm...",
    "volume": 0.15,
    "fade_out_seconds": 5
  },
  "script": "Your full script text here. No stage directions — pure spoken word."
}
```

**Or use a script file:**
```json
{
  "script_file": "events/podcast/scripts/shao_script.txt",
  ...
}
```

## Plan Parameters

| Field | Required | Description |
|-------|----------|-------------|
| `topic` | ✓ | Single-word or short topic label |
| `thesis` | ✓ | One sentence: what this episode argues or explores |
| `duration_minutes` | ✓ | Target duration (1–30). Used to validate script length |
| `language` | ✓ | `zh` (Chinese), `en` (English), `ja` (Japanese), etc. |
| `persona.voice_id_file` | ✓ | Path to voice ID file (e.g. `life/voice_id.txt`) |
| `persona.speed` | — | Speech rate (default: 1.0). 0.8–0.9 = calm/reflective |
| `persona.pitch` | — | Pitch offset (default: 0). -1 to -2 = lower/warmer |
| `persona.vol` | — | Volume (default: 1.0) |
| `music.style` | — | Music generation prompt. Omit for voice-only |
| `music.lyrics` | — | Minimal lyrics/humming for music gen |
| `music.volume` | — | BGM mix level (default: 0.15). Keep under 0.25 |
| `music.fade_out_seconds` | — | Fade BGM out at end (default: 5) |
| `script` | ✓* | Full script text (inline) |
| `script_file` | ✓* | Path to script file (alternative to `script`) |

*One of `script` or `script_file` required.

## Script Writing Constraints

See `references/script-guide.md` for the full framework. Quick rules:

**Three non-negotiables (must be explicit in the plan):**
1. `duration_minutes` — controls depth and density
2. `thesis` — one clear narrative thread; if two things are being said, it's two episodes
3. `persona` — whose voice, what tone, what speed

**Sonic constraints (sentences must work when spoken):**
- Short sentences. No nested clauses. No parentheses.
- Vary sentence length — short punchy + longer flowing alternating
- Punctuation = breath. Commas and periods control pacing.
- ~200 chars/min for Chinese, ~130 words/min for English

**Structural arc (required):**
- Hook (first 15 seconds must earn the next 3 minutes)
- Tension/development (one thread, deepened — not multiplied)
- Landing (last lines must feel complete; open endings are intentional, not lazy)

**Music integration (if using music):**
- Script should have natural pause points where music can breathe
- Don't mark stage directions in the script — keep it pure spoken word
- BGM is background; voice is foreground; never compete

## Voice Mood Presets

| Mood | Speed | Pitch | Vol |
|------|-------|-------|-----|
| Neutral | 1.0 | 0 | 1.0 |
| Reflective / Essay | 0.85 | -1 | 1.0 |
| Intimate / Confessional | 0.9 | -2 | 0.8 |
| Urgent / Direct | 1.05 | 0 | 1.1 |
| Melancholic | 0.8 | -2 | 0.7 |

## Common Mistakes

- **Stage directions in script** — `[MUSIC IN]` doesn't get spoken naturally. Remove all markers.
- **Script too long for duration** — validate before generating. 4 min Chinese = ~800 chars
- **Single thesis, multiple topics** — one podcast = one idea. Split if needed.
- **BGM too loud** — `volume: 0.25` is the ceiling. Above that it competes with voice.
- **Flat sentence length** — if every sentence is the same length, TTS sounds robotic.
- **No arc** — a list of observations is not a podcast. There must be tension and release.
