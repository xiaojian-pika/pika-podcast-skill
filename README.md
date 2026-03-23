# pika-podcast-skill

Podcast generation skill for Pika AI agents.

## Pipeline

```
plan.json → TTS (MiniMax voice) → BGM (MiniMax music) → Mix (ffmpeg) → MP3
```

## Quick Start

```bash
python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py validate plan.json
python $PIKABOT_SKILLS_DIR/podcast/scripts/generate.py generate --plan plan.json --name "episode_name"
```

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
    "style": "minimalist ambient piano, sparse slow notes",
    "lyrics": "[intro]\nMm...\n[outro]\nMm...",
    "volume": 0.15,
    "fade_out_seconds": 5
  },
  "script_file": "events/podcast/plans/episode_script.txt"
}
```

See `SKILL.md` for full documentation and `references/script-guide.md` for script writing constraints.

## Dependencies

- `minimax-voice` skill (TTS)
- `minimax-music` skill (BGM generation)
- `ffmpeg` (mixing)
