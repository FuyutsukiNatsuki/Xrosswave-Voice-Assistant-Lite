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

from typing import Optional, Tuple

import numpy as np

DEFAULT_FFT_SIZE = 2048      # ~46 ms window @ 44.1 kHz → ~21.5 Hz resolution
DEFAULT_MAX_FREQ = 6400.0    # display ceiling (Hz)
_EPS = 1e-12

# Narrowband: long window (fine frequency resolution; harmonics as stripes).
NARROWBAND_WINDOW = 2048
NARROWBAND_FFT = 2048
# Wideband: short window (fine time resolution; formant bands, pitch striations).
WIDEBAND_WINDOW = 256        # ~5.8 ms → ~172 Hz resolution
WIDEBAND_FFT = 1024          # zero-padded for a smoother display
WIDEBAND_HOP = 256           # columns every ~5.8 ms (≈8× the narrowband column rate)


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
    window_size: Optional[int] = None,
    fft_size: int = DEFAULT_FFT_SIZE,
    max_freq: float = DEFAULT_MAX_FREQ,
) -> np.ndarray:
    """One spectrogram column: dB magnitude per frequency bin.

    Uses the most recent ``window_size`` samples (Hann-windowed), zero-padded to
    ``fft_size``. ``window_size`` sets the true frequency resolution (long =
    narrowband, short = wideband); ``fft_size`` only sets the display bin
    density. Defaults to ``window_size == fft_size`` (narrowband). Returns a 1-D
    float32 array aligned with :func:`column_frequencies`.
    """
    if window_size is None:
        window_size = fft_size
    frame = samples[-window_size:]
    if frame.size < window_size:
        frame = np.pad(frame, (window_size - frame.size, 0))
    windowed = frame.astype(np.float64) * np.hanning(window_size)
    if window_size < fft_size:  # zero-pad up to the FFT size
        windowed = np.pad(windowed, (0, fft_size - window_size))
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
        cols.append(
            spectrum_column(samples[:start], samplerate, fft_size=fft_size, max_freq=max_freq)
        )
    image = np.array(cols, dtype=np.float32) if cols else np.zeros((0, freqs.size), np.float32)
    return freqs, image
