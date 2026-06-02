"""Narrowband spectrogram column extraction.

A spectrogram is built one time-column at a time. "Narrowband" means a long
analysis window (fine frequency resolution — harmonics show as horizontal
stripes), as opposed to "wideband" (short window, fine time resolution).

We window the most recent ``fft_size`` samples with a Hann window and take the
magnitude spectrum in dB. At 44.1 kHz, ``fft_size=2048`` is a ~46 ms window →
~21.5 Hz resolution, which is firmly narrowband for voice.

The pipeline computes one column per chunk off the GUI thread; the GUI stacks
columns into a scrolling waterfall.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

DEFAULT_FFT_SIZE = 2048      # ~46 ms window @ 44.1 kHz → ~21.5 Hz resolution
DEFAULT_MAX_FREQ = 5000.0    # display ceiling (Hz)
_EPS = 1e-12


def column_frequencies(
    samplerate: int,
    fft_size: int = DEFAULT_FFT_SIZE,
    max_freq: float = DEFAULT_MAX_FREQ,
) -> np.ndarray:
    """Frequencies (Hz) of the bins returned by :func:`spectrum_column`."""
    freqs = np.fft.rfftfreq(fft_size, 1.0 / samplerate)
    return freqs[freqs <= max_freq]


def spectrum_column(
    samples: np.ndarray,
    samplerate: int,
    fft_size: int = DEFAULT_FFT_SIZE,
    max_freq: float = DEFAULT_MAX_FREQ,
) -> np.ndarray:
    """One narrowband spectrogram column: dB magnitude per frequency bin.

    Uses the most recent ``fft_size`` samples (left-padded with zeros if the
    input is shorter). Returns a 1-D float32 array aligned with
    :func:`column_frequencies`.
    """
    frame = samples[-fft_size:]
    if frame.size < fft_size:
        frame = np.pad(frame, (fft_size - frame.size, 0))
    windowed = frame.astype(np.float64) * np.hanning(fft_size)
    spectrum = np.fft.rfft(windowed)
    power = (np.abs(spectrum) ** 2) / fft_size
    db = 10.0 * np.log10(power + _EPS)
    n = column_frequencies(samplerate, fft_size, max_freq).size
    return db[:n].astype(np.float32)


def spectrogram(
    samples: np.ndarray,
    samplerate: int,
    hop: int,
    fft_size: int = DEFAULT_FFT_SIZE,
    max_freq: float = DEFAULT_MAX_FREQ,
) -> Tuple[np.ndarray, np.ndarray]:
    """Offline helper: stack columns over a whole signal (for verification).

    Returns ``(freqs, image)`` where ``image`` is shape ``(n_columns, n_freq)``.
    """
    freqs = column_frequencies(samplerate, fft_size, max_freq)
    cols = []
    for start in range(fft_size, samples.size + 1, hop):
        cols.append(spectrum_column(samples[:start], samplerate, fft_size, max_freq))
    image = np.array(cols, dtype=np.float32) if cols else np.zeros((0, freqs.size), np.float32)
    return freqs, image
