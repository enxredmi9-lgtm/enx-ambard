# Samsalino Tandirino

A 60-second vertical YouTube Short (1080×1920, 30 fps, MP4): a loud,
bright "brainrot" nursery rhyme about four Uzbek-flavoured characters.

| Character | What it is |
|---|---|
| **Samsalino Tandirino** | golden samsa in sneakers, jumps out of a clay tandir |
| **Plovolino Kazanino** | rocket-powered kazan of plov, rains carrots over rooftops |
| **Dutarini Crocodini** | crocodile in a blue doppi playing the dutar, with a dancing wolf |
| **Chaynikoni Pialoni** | blue-and-white teapot riding a pony, pours green tea into a piala |

## Build

Needs Python 3.10+ and `ffmpeg` on PATH.

```bash
pip install -r requirements.txt
python make_video.py              # -> output/samsalino.mp4 (~5 min on 4 cores)
python make_video.py --preview 5 30 55   # quick PNG stills instead
```

Options: `--tts auto|edge|kokoro|espeak`, `--workers N`, `--out PATH`, `--assets DIR`.

## How it works

- **characters.py**: every character, prop and background is drawn with Pillow
  (thick outlines, big eyes, flat colours) and supersampled for smooth edges.
- **audio.py**:
  - Narration uses **edge-tts** (`en-US-GuyNeural`, slowed down). Each lyric
    line is placed in its time slot, with a short silence before every
    character's name, and gently sped up if it runs long.
  - The title and final line get an echo.
  - A 120 BPM kick, clap and hi-hat beat is synthesised with numpy. It speeds
    up to 132 BPM in the second chorus and 140 BPM in the finale, then builds
    with a clap roll into a final BOOM. The beat is turned down under the
    voice.
  - If edge-tts can't reach Microsoft's service, it falls back to
    **Kokoro** (an offline neural voice, model downloaded automatically from
    GitHub into `.models/`), then to `espeak-ng`.
- **make_video.py**:
  - Holds the timeline: lyrics, scenes, and beat-synced bounce, squash and
    wobble.
  - Draws burned-in subtitles.
  - Renders frames in parallel and encodes them with ffmpeg (H.264 + AAC).

## Using your own art

Create `assets/` next to `make_video.py` and drop in any of these PNGs
(transparent background). Each one replaces the drawn version; motion and
timing stay the same:

`samsalino.png`, `plovolino.png`, `dutarini.png`, `chaynikoni.png`,
`wolf.png`, `pony.png`, `tandir.png`, `piala.png`, `carrot.png`,
`background.png` (courtyard), `rooftops.png`.

## Credits

Font: [Luckiest Guy](https://fonts.google.com/specimen/Luckiest+Guy) by Astigmatic,
Apache License 2.0 (`fonts/LuckiestGuy-LICENSE.txt`).
