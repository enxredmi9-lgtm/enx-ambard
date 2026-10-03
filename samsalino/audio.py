"""Narration (edge-tts, with offline fallbacks), a numpy drum beat, and the mix."""
import asyncio
import hashlib
import os
import shutil
import subprocess
import urllib.request
import wave

import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache", "tts")
MODELS = os.path.join(HERE, ".models")

EDGE_VOICE = "en-US-GuyNeural"
EDGE_RATE = "-12%"      # slightly slow, dramatic
EDGE_PITCH = "-6Hz"
KOKORO_VOICE = "am_michael"
KOKORO_SPEED = 0.88
KOKORO_URL = ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
              "model-files-v1.0/")


# ------------------------------------------------------------------ utils
def decode(path, tempo=1.0):
    """Decode any audio file to mono float32 at SR, optionally time-stretched."""
    filters = []
    t = tempo
    while t > 2.0:
        filters.append("atempo=2.0")
        t /= 2.0
    while t < 0.5:
        filters.append("atempo=0.5")
        t /= 0.5
    if abs(t - 1.0) > 1e-3:
        filters.append(f"atempo={t:.4f}")
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim_silence(x, thresh=0.02):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(0.01 * SR))
    b = min(len(x), idx[-1] + int(0.05 * SR))
    return x[a:b]


def write_wav(path, stereo):
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ TTS
def _edge(text, out_mp3):
    import certifi
    # Honour a custom CA bundle (corporate / sandbox TLS proxies).
    if os.environ.get("SSL_CERT_FILE"):
        certifi.where = lambda: os.environ["SSL_CERT_FILE"]
    import edge_tts

    async def run():
        com = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH)
        await com.save(out_mp3)
    asyncio.run(run())
    if not os.path.exists(out_mp3) or os.path.getsize(out_mp3) == 0:
        raise RuntimeError("edge-tts produced no audio")


_kokoro = None


def _kokoro_model():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        os.makedirs(MODELS, exist_ok=True)
        for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            dst = os.path.join(MODELS, name)
            if not os.path.exists(dst):
                print(f"  downloading {name} ...")
                urllib.request.urlretrieve(KOKORO_URL + name, dst + ".part")
                os.replace(dst + ".part", dst)
        _kokoro = Kokoro(os.path.join(MODELS, "kokoro-v1.0.onnx"),
                         os.path.join(MODELS, "voices-v1.0.bin"))
    return _kokoro


def _kokoro_tts(text, out_wav):
    import soundfile as sf
    samples, sr = _kokoro_model().create(text, voice=KOKORO_VOICE,
                                         speed=KOKORO_SPEED, lang="en-us")
    sf.write(out_wav, samples, sr)


def _espeak(text, out_wav):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng not installed")
    subprocess.run([exe, "-v", "en-us+m3", "-s", "135", "-p", "30", "-a", "180",
                    "-w", out_wav, text], check=True)


BACKENDS = {"edge": (_edge, ".mp3"), "kokoro": (_kokoro_tts, ".wav"),
            "espeak": (_espeak, ".wav")}


class Narrator:
    """Synthesises lines with the first backend that works, caching results."""

    def __init__(self, preferred="auto"):
        self.order = (["edge", "kokoro", "espeak"] if preferred == "auto"
                      else [preferred])
        self.backend = None
        os.makedirs(CACHE, exist_ok=True)

    def _path(self, backend, text):
        h = hashlib.sha1(f"{backend}|{EDGE_VOICE}|{KOKORO_VOICE}|{text}".encode())
        return os.path.join(CACHE, f"{backend}_{h.hexdigest()[:16]}"
                            + BACKENDS[backend][1])

    def say(self, text):
        candidates = [self.backend] if self.backend else self.order
        last = None
        for b in candidates:
            path = self._path(b, text)
            try:
                if not os.path.exists(path):
                    BACKENDS[b][0](text, path)
                if self.backend != b:
                    print(f"  narrator voice: {b}")
                self.backend = b
                return path
            except Exception as e:  # fall through to next backend
                last = e
                if os.path.exists(path):
                    os.remove(path)
                print(f"  TTS backend '{b}' unavailable: {type(e).__name__}: "
                      f"{str(e).splitlines()[0][:120] if str(e) else ''}")
        raise RuntimeError(f"No TTS backend worked (last error: {last})")


def echo(x, delays=(0.21, 0.42, 0.63, 0.84), gains=(0.55, 0.35, 0.2, 0.1)):
    n = len(x) + int(max(delays) * SR) + 1
    y = np.zeros(n, dtype=np.float32)
    y[:len(x)] += x
    for d, g in zip(delays, gains):
        o = int(d * SR)
        y[o:o + len(x)] += g * x
    return y


def render_voice(lines, narrator, total):
    """lines: dicts with t0, t1, tts, pause, gain, echo. Returns mono track and
    the actual (start, end) time of each line's audio."""
    track = np.zeros(int(total * SR) + SR, dtype=np.float32)
    spans = []
    for ln in lines:
        path = narrator.say(ln["tts"])
        clip = trim_silence(decode(path))
        start = ln["t0"] + ln.get("pause", 0.0)
        avail = ln["t1"] - start - 0.04
        dur = len(clip) / SR
        if dur > avail:
            clip = trim_silence(decode(path, tempo=dur / avail))
            clip = clip[:int(avail * SR)]
            clip[-200:] *= np.linspace(1, 0, min(200, len(clip)))
        clip = clip / (np.max(np.abs(clip)) + 1e-9) * 0.9 * ln.get("gain", 1.0)
        if ln.get("echo"):
            clip = echo(clip)
        a = int(start * SR)
        b = min(len(track), a + len(clip))
        track[a:b] += clip[:b - a]
        spans.append((start, start + min(dur, avail)))
    return track[:int(total * SR)], spans


# ------------------------------------------------------------------ drums
def _kick(length=0.35, punch=1.0):
    t = np.arange(int(length * SR)) / SR
    freq = 48 + 120 * np.exp(-t * 28) * punch
    ph = 2 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * (8 / max(length / 0.35, 1e-3)))
    click = np.exp(-t * 400) * 0.6
    return ((np.sin(ph) * env) + click * np.random.default_rng(1).uniform(
        -1, 1, len(t))).astype(np.float32)


def _clap(seed=2):
    rng = np.random.default_rng(seed)
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    # crude band-pass: high-pass by differencing, then smooth
    hp = np.diff(noise, prepend=0)
    bp = np.convolve(hp, np.ones(4) / 4, mode="same")
    env = np.zeros(n)
    for o in (0.0, 0.011, 0.022):
        k = int(o * SR)
        env[k:] += np.exp(-(t[:n - k]) * (60 if o < 0.02 else 16))
    return (bp * env * 1.3).astype(np.float32)


def _hat(seed=3):
    rng = np.random.default_rng(seed)
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.uniform(-1, 1, n + 1))
    return (noise * np.exp(-t * 70) * 0.5).astype(np.float32)


def _crash(length=1.8, seed=4):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.uniform(-1, 1, n + 1))
    return (noise * np.exp(-t * 2.2) * 0.8).astype(np.float32)


def _add(track, sample, t, gain=1.0):
    a = int(t * SR)
    if a >= len(track) or a < 0:
        return
    b = min(len(track), a + len(sample))
    track[a:b] += sample[:b - a] * gain


def make_drums(beats, total, start, roll, boom, intro_boom=0.0):
    """Kick on every beat, clap on 2 and 4, off-beat hats, a clap roll build,
    and a final BOOM."""
    tr = np.zeros(int(total * SR), dtype=np.float32)
    kick, clap, hat = _kick(), _clap(), _hat()
    big = _kick(1.4, punch=1.4)
    _add(tr, big, intro_boom, 1.0)
    _add(tr, _crash(), intro_boom, 0.35)
    for i, bt in enumerate(beats):
        if bt < start - 1e-6 or bt >= boom - 1e-6:
            continue
        nxt = beats[i + 1] if i + 1 < len(beats) else bt + 0.5
        in_roll = roll[0] <= bt < roll[1]
        _add(tr, kick, bt, 1.0)
        if not in_roll:
            if i % 2 == 1:
                _add(tr, clap, bt, 0.75)
            _add(tr, hat, (bt + nxt) / 2, 0.5)
    # accelerating clap roll with rising volume
    t = roll[0]
    while t < roll[1]:
        p = (t - roll[0]) / (roll[1] - roll[0])
        _add(tr, clap, t, 0.35 + 0.6 * p)
        t += 0.125 - 0.075 * p
    _add(tr, big, boom, 1.25)
    _add(tr, _crash(2.0), boom, 0.6)
    # little pickup fill into the first chorus
    for k, ft in enumerate(np.arange(start - 0.5, start, 0.125)):
        _add(tr, clap, ft, 0.3 + 0.12 * k)
    return tr


def mix(voice, drums, drum_gain=0.42):
    # duck the beat under the narrator
    env = np.abs(voice)
    win = int(0.05 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    env = np.clip(env / (env.max() + 1e-9) * 3, 0, 1)
    duck = 1.0 - 0.35 * env
    m = voice * 1.0 + drums * drum_gain * duck
    m = np.tanh(m * 1.15) / np.tanh(1.15)       # soft limiter
    m = m / (np.max(np.abs(m)) + 1e-9) * 0.95
    return np.stack([m, m], axis=1)
