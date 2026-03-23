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

# Podcast Skill

You are the voice. Write a plan JSON with your script and production parameters, then `generate.py` handles TTS + music + mixing.

**Before writing any script**, read `references/script-guide.md` — it defines the constraint framework for good podcast scripts. Read your SOUL.md and identity files first. If another agent could read your script unchanged, rewrite it.

## Quick Start

```bash
# 1. Write your plan (see Plan Format below)
# 2. Save to events/podcast/plans/ (NOT /tmp — lost on restart)
# 3. Validate it
python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py validate events/podcast/plans/my_ep.json

# 4. Generate
python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py generate \
  --plan events/podcast/plans/my_ep.json --name "my_episode"
```

**Always spawn a subagent for generation** — takes 4–6 minutes. Never block the main session.

Final output line: `AUDIO:generated/podcast/{name}_{hash}.mp3`

---

## Plan Format (v2 — Multi-Segment with Music Cues)

This is the production-grade format. Use it for all new episodes.

```json
{
  "meta": { "version": 1 },
  "topic": "少",
  "thesis": "少不是减法——是一种对什么值得存在的判断",
  "duration_minutes": 4,
  "language": "zh",
  "script_file": "events/podcast/plans/my_script.txt",
  "voice": {
    "voice_id": "ttv-voice-XXXXXXXX",
    "language": "zh",
    "speed": 0.88,
    "pitch": -1,
    "vol": 1.0,
    "speed_overrides": {
      "seg_pre": 0.88,
      "seg_1": 0.93,
      "seg_2": 0.86,
      "seg_3": 0.84,
      "seg_conclusion": 0.87
    }
  },
  "music_library": {
    "piano_motif": {
      "style": "solo acoustic piano, slow gentle arpeggios, atmospheric, sparse but continuous, soft sustained chords, dreamlike and still, [instrumental]",
      "lyrics": "[instrumental]",
      "base_duration_s": 90,
      "loopable": true,
      "loop_if_short": true
    },
    "cello_drone": {
      "style": "single sustained cello tone, extremely long bowing, no vibrato, no rhythm, no melody, no movement, barely audible ambient resonance, [instrumental]",
      "lyrics": "[instrumental]",
      "base_duration_s": 120,
      "loopable": true,
      "loop_if_short": true
    }
  },
  "music_cues": [
    {
      "id": "open",
      "keyword": "MUSIC IN",
      "asset_id": "piano_motif",
      "vol": 0.10,
      "fade_in_s": 4,
      "fade_out_s": 2,
      "duration_source": "through_next_cue",
      "duration_buffer_s": 5
    },
    {
      "id": "body",
      "keyword": "CELLO IN",
      "asset_id": "cello_drone",
      "vol": 0.07,
      "fade_in_s": 3,
      "fade_out_s": 3,
      "duration_source": "through_next_cue",
      "duration_buffer_s": 5
    },
    {
      "id": "close",
      "keyword": "MUSIC OUT",
      "asset_id": "piano_motif",
      "vol": 0.10,
      "fade_in_s": 4,
      "fade_out_s": 12,
      "duration_source": "next_tts_segment",
      "duration_buffer_s": 20
    }
  ],
  "mix": {
    "output_bitrate": "192k",
    "volume_envelope": {
      "intro_end_s": 30,
      "transition_s": 10,
      "body_vol": 0.35
    }
  }
}
```

---

## Script File Format (with Music Markers)

The script uses markers to define music cue points and pauses. Markers must match `keyword` fields in `music_cues`.

```text
[MUSIC IN]

这是一段开场白，在音乐进入之前稍作沉默，然后开始讲述。

[PAUSE 1.5s]

这里是第一段正文内容。

[CELLO IN]

这里是第二段，更安静的部分，大提琴在背后支撑。

[PAUSE 1.5s]

继续讲述...

[MUSIC OUT]

这里是结尾，钢琴回归。
```

**Marker rules:**
- Markers go on their own line, wrapped in `[...]`
- `[PAUSE Xs]` inserts X seconds of silence (exact syntax required)
- `[MUSIC IN]`, `[CELLO IN]`, `[MUSIC OUT]` etc. trigger cue by `keyword` match
- A music cue plays from its marker until the next music cue (if `through_next_cue`), or for one TTS segment (if `next_tts_segment`)
- **NEVER put phonetic annotations in the script** — TTS will read them as literal text

---

## Voice Configuration

### Using Voice Design (Recommended for Chinese)

For Chinese podcasts, use MiniMax voice design API to create a designed voice — far better Chinese pronunciation than cloned English voices.

```python
# Create a designed voice (one-time setup)
POST /proxy/minimax/v1/voice_design
{
  "prompt": "年轻女性导演，声音低沉温柔，节奏舒缓，中文韵律感强，温暖有质感",
  "preview_text": "少，不是减法。是一种判断。"
}
# → returns voice_id: "ttv-voice-XXXXXXXX"
```

Then use the voice_id directly in the plan:
```json
"voice": { "voice_id": "ttv-voice-XXXXXXXX" }
```

Or use `voice_id_file` to reference a file containing the voice ID:
```json
"voice": { "voice_id_file": "life/voice_id.txt" }
```

### Per-Segment Speed Overrides

Different topics warrant different speaking rates. Use `speed_overrides` keyed by segment ID (auto-generated as `seg_pre`, `seg_1`, `seg_2` etc. matching script order):

```json
"speed_overrides": {
  "seg_pre": 0.88,
  "seg_1": 0.93,
  "seg_2": 0.86,
  "seg_3": 0.84
}
```

Recommended ranges: 0.84 (slowest, most reflective) → 0.93 (faster, conversational)

---

## Music Production Rules

### Music Library Deduplication

The `music_library` defines named assets. Each asset is generated **once** and reused by multiple cues. This avoids redundant API calls and ensures consistency.

- `base_duration_s`: maximum duration you'll need from this asset
- `loopable: true` + `loop_if_short: true`: required when MiniMax returns a short clip (common for piano/ambient)

### Volume Architecture

**Critical: do NOT use per-cue `vol` to shape the overall loudness arc.**

Instead:
1. Set per-cue `vol` to natural instrument levels (piano: 0.10, cello: 0.07)
2. Use `mix.volume_envelope` to apply a smooth arc to the entire assembled music track

The `volume_envelope` config:
```json
"volume_envelope": {
  "intro_end_s": 30,      // full volume for first 30s
  "transition_s": 10,     // 10s fade to body level
  "body_vol": 0.35        // relative level during main narration (35% of full)
  // close: symmetric — rises back to 1.0 10s before end
}
```

This creates a smooth broadcast-style ducking arc:
`[1.0 intro] → [fade] → [0.35 body] → [fade] → [1.0 close]`

### Music Style Guidelines

| Use case | Style descriptor | Notes |
|----------|-----------------|-------|
| Reflective intro/outro | `solo acoustic piano, slow arpeggios, atmospheric, [instrumental]` | Always use `[instrumental]` — no humming/chanting prompts |
| Body / quiet background | `single sustained cello tone, no vibrato, no rhythm, [instrumental]` | Keep vol very low (0.06–0.08); avoid rhythmic movement |
| Sparse interlocutor | `sparse single piano notes, each note resonates fully before next, breathing presence` | Wenghao style: piano as "other voice" not background fill |
| Energetic/upbeat | `uptempo acoustic guitar, gentle rhythm, warm` | Don't compete with voice |

**Avoid:**
- `tintinnabuli` or reverb-heavy sparse styles → creates silent zones (appears as -17dB with no audible content for 10+ seconds)
- Any lyrics or humming in the style prompt → MiniMax may generate female vocal chanting that drowns the host voice
- Aggressive rhythmic movement for cello → sounds intrusive; cello should be atmosphere only

### Duration Sources

| `duration_source` | Behavior |
|-------------------|----------|
| `through_next_cue` | Music spans from this cue marker to the next music cue, summing all TTS + pause durations between them + `duration_buffer_s` |
| `next_tts_segment` | Music spans the duration of the next TTS segment only |
| (fixed number) | Music plays for exactly that many seconds |

---

## Production Gotchas (Hard-Won Lessons)

### 1. Phonetic annotations in script → TTS reads them aloud

**Wrong:** `「减少」的少（shǎo）` → TTS says "jiǎn shǎo de shǎo shǎo"
**Right:** Just write `「减少」的少` — designed Chinese voices handle tones natively

Never add `（shǎo）`, `[音：shǎo]`, or any other inline annotation. The TTS engine treats them as literal text.

### 2. Music stops at ~22s despite longer base_duration

MiniMax sometimes returns a clip shorter than `base_duration_s`. Without `loopable: true` + `loop_if_short: true`, the music track goes silent.

**Fix:** Always set both on any ambient/pad asset:
```json
"loopable": true,
"loop_if_short": true
```

### 3. Female vocal chanting appears in opening

If the music style prompt contains any humming or lyric hint (`Mm...`, `vocal`, `choir`), MiniMax may add female chanting.

**Fix:** Always end the style with `[instrumental]` and set `"lyrics": "[instrumental]"`.

### 4. Music disappears at exactly 30s

This was a `through_next_cue` implementation bug (v1–v10) — the code fell back to `float(cue.get("duration_s", 30))` = 30s when `duration_source` was unrecognized. Fixed in current generate.py.

If you see music cutting off at a round number, check your `duration_source` values.

### 5. Per-cue vol creates abrupt jumps

Setting different `vol` values per cue creates sharp volume steps between sections, not a smooth arc. Use `mix.volume_envelope` instead for gradual shaping.

### 6. Cloned English voice sounds foreign in Chinese

A voice cloned from English audio has no Chinese tonal patterns. Use MiniMax `/v1/voice_design` to create a new Chinese-native designed voice instead.

---

## Pronunciation Issues

If a Chinese word is consistently mispronounced (wrong tone due to context):

1. **First try:** rewrite the surrounding sentence to change context
2. **Second try:** check if the word appears in a phrase where the tone naturally shifts (e.g., 少 in 少年 vs 减少 vs standalone 少)
3. **Don't:** add inline phonetic annotations — they get read aloud as extra text
4. **Don't:** use SSML phoneme markup unless the TTS API explicitly supports it

---

## Voice Mood Presets

| Mood | Speed | Pitch | Notes |
|------|-------|-------|-------|
| Neutral | 1.0 | 0 | Default |
| Reflective / Essay | 0.85–0.88 | -1 | Calm, considered |
| Intimate / Confessional | 0.88–0.90 | -2 | Slower, warmer |
| Urgent / Direct | 1.05 | 0 | Faster, cleaner |
| Melancholic | 0.82–0.85 | -2 | Slowest, lowest |

For per-segment variation, use `speed_overrides` to match topic/mood within an episode.

---

## Common Mistakes

- **Script too long for duration** — validate before generating. 4 min Chinese ≈ 800 chars
- **Single thesis, multiple topics** — one podcast = one idea. Split if needed.
- **No arc** — a list of observations is not a podcast. There must be tension and release.
- **Per-cue vol for arc shaping** — use `mix.volume_envelope` instead
- **Flat sentence length** — if every sentence is the same length, TTS sounds robotic
- **Stage directions in script** — markers like `[MUSIC IN]` work; don't invent new ones not in `music_cues`
- **Saving plan to /tmp** — always save to `events/podcast/plans/` or plans are lost on restart
