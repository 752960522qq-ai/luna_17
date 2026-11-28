"""Mix three fingerprinted public-domain field recordings for the storm mission."""
import hashlib
import subprocess

import numpy as np
from scipy.signal import butter, sosfiltfilt

from .sound import RATE


SOURCES = {
    "rain-ezwa.ogg": "31efcbe952a3989a9276774e2d7be61a2dc98fdd785a94d1435fc19cda9a84d1",
    "thunder-caesar.ogg": "cbfd7b7504bc4e53d6e56ac8d933ba56f97cc28f15a46800c74c2d8eccb3fa89",
    "thunder-guan.ogg": "5c3b89ab57f640bca4483982b456e317c139aac8be47a5e11402afab55fabf94",
}


def read(root, name, start, end, frequency):
    path = root / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCES[name]:
        raise ValueError(f"Unexpected download: {name}")
    # Decode before slicing so the cut points do not depend on container seeking.
    pcm = np.frombuffer(subprocess.check_output([
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-",
    ]), dtype="<f4")
    lo, hi = (round(t * RATE) for t in (start, end))
    if hi > len(pcm):
        raise ValueError(f"Recording is shorter than the selected excerpt: {name}")
    return sosfiltfilt(butter(3, frequency, fs=RATE, btype="bandpass", output="sos"), pcm[lo:hi])


def pcm(x, rms_db, peak):
    rms = float(np.sqrt(np.mean(np.square(x))))
    if not np.isfinite(rms) or rms < 1e-5:
        raise ValueError("Invalid or silent weather recording")
    g = min(10 ** (rms_db / 20) / rms, peak / np.max(np.abs(x)))
    return np.rint(x * g * 32767).astype("<i2")


def fades(x, start, end):
    x[:start] *= np.sin(np.linspace(0, np.pi / 2, start)) ** 2
    x[-end:] *= np.cos(np.linspace(0, np.pi / 2, end)) ** 2
    return x


def field_recordings(root):
    rain = read(root, "rain-ezwa.ogg", 7, 44.6, (78, 10400))
    n = round(1.6 * RATE)
    angle = np.linspace(0, np.pi / 2, n)
    # At the wrap point, the last crossfade sample and first body sample
    # are consecutive samples from the original head. Neither end is silent.
    bed = np.concatenate((rain[n:-n], rain[-n:] * np.cos(angle) + rain[:n] * np.sin(angle)))
    roll = read(root, "thunder-caesar.ogg", 2.6, 11.6, (24, 1420))
    crack = read(root, "thunder-guan.ogg", 88.34, 91.76, (28, 9200))
    return {
        "rain": pcm(bed, -22, .62),
        "roll": pcm(fades(roll, round(.085 * RATE), RATE), -19, .77),
        "crack": pcm(fades(crack, round(.025 * RATE), round(.55 * RATE)), -15.5, .89),
    }
