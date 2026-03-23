# Script Writing Guide

This guide defines the constraint framework for podcast scripts. Follow it every time.

## The Three Non-Negotiables

These must be explicit in the plan before writing a single word:

### 1. Duration Target
- Determines everything: depth, word count, number of beats
- **Chinese:** ~200 characters/minute at natural speaking pace
- **English:** ~130 words/minute
- 3 min = 600 chars (zh) / 390 words (en)
- 5 min = 1000 chars (zh) / 650 words (en)
- Validate with `generate.py validate` before generating

### 2. Single Narrative Thread
- One question or one tension. Not two.
- If you have two ideas: pick one, or make the *relationship between them* the single idea
- A podcast that tries to say everything says nothing
- Test: can the thesis be stated in one sentence? If not, rethink.

### 3. Persona Parameterization
- Whose voice is speaking?
- What is their relationship to this topic?
- What tone are they taking? (observational, confessional, provocative, elegiac)
- Speed and pitch should reflect emotional register, not just defaults

---

## Narrative Arc (Required)

Every podcast needs:

**Hook (first 15–30 seconds)**
- Must earn the next few minutes
- Don't open with definitions or context. Open with a scene, a question, or a contradiction.
- Good: *"1988年，Mark Hollis把乐手们带进录音棚，告诉他们一件事..."*
- Bad: *"Today I want to talk about minimalism in music..."*

**Development**
- One thread, deepened — not multiplied
- Use 2–3 concrete examples. Not 7.
- Each example should add a new dimension to the thesis, not just repeat it
- Tension = the thing that makes the thesis uncomfortable or surprising

**Landing**
- The last lines are the most important. They land.
- Open endings are fine — but they must be *intentionally* open, not just trailing off
- The listener should feel the episode completed, even if the question wasn't answered
- Often the best landing returns to the opening image, transformed

---

## Sonic Writing Rules

Podcast scripts are *heard*, not read.

**Sentence length variation (critical)**
- Alternate short and long sentences. Single rhythm = robotic TTS.
- Short punch. Then a longer thought that has room to breathe and develop.
- Then short again.
- Don't write like an essay. Write like you're talking.

**Punctuation = breath**
- Commas create micro-pauses. Use them intentionally.
- Periods create full stops. Don't be afraid of them mid-thought.
- Em-dashes (——) create dramatic pauses. Use sparingly.
- No brackets, footnotes, or parentheses — the listener can't see them.

**Sentence construction**
- Avoid nested clauses: *"The thing that, despite being technically complex, somehow..."* — bad
- Keep subject close to verb: *"He stopped. No explanation. Just silence."* — good
- Avoid passive voice — it sounds distant when spoken
- Contractions and fragments are fine in conversational register

**Foreign words and names**
- Spell out how they should sound if unclear
- For Chinese podcasts: mix of English proper nouns is fine (musicians, film titles) but keep Chinese sentence structure

---

## Music Integration

Music is background, not accompaniment. Rules:

- BGM volume: 0.12–0.20 is the sweet spot. Below 0.12 = inaudible. Above 0.25 = competing.
- Fade out: last 5 seconds of episode, BGM fades out with the voice
- Music style should match emotional register: reflective essay → sparse piano, ambient; energetic → uptempo but not intrusive
- The script doesn't need to acknowledge the music — it just breathes around it

**Do NOT include music cues in the script text.** No `[MUSIC IN]`, `[FADE]`, etc. The script is pure spoken word. Music is a production layer handled by generate.py.

---

## Persona Abstraction

If building this skill for multiple agents, each agent needs different defaults:

| Dimension | What changes |
|-----------|-------------|
| Voice ID | Different cloned voice |
| Tone | Some agents are warmer, some drier, some more intellectual |
| Speed | Default speed reflects personality (fast = energetic, slow = contemplative) |
| Language | Default language of the agent |
| Topic affinity | What topics feel authentic vs. forced |

The `persona` block in the plan makes this explicit. Never hardcode personality into the script — write the script for the persona, but keep the persona parameters in the plan.

---

## Self-Check Before Generating

Before running `generate.py`, ask:

1. Is the thesis one sentence? Can I say what this episode argues in one sentence?
2. Does the opening earn the next few minutes?
3. Are there sentences I couldn't read aloud comfortably? Rewrite them.
4. Does it end — not stop? Is the last line the right last line?
5. Is the script length within ~10% of target? (`generate.py validate` will check)
6. Would another agent use this script unchanged? If yes, it's not personal enough.
