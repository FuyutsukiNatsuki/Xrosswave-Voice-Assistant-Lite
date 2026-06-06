"""Deterministic narrowband spectrogram check.

Confirms:
  * a pure tone peaks at its frequency, and
  * two close tones (300 & 360 Hz, 60 Hz apart) resolve as TWO separate peaks
    — this is the point of narrowband: ~21.5 Hz resolution < 60 Hz spacing.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_spectrogram_synthetic.py
"""

import _bootstrap  # noqa: F401

import numpy as np

from xvalite.analysis.spectrogram import (
    DEFAULT_FFT_SIZE,
    column_frequencies,
    spectrum_column,
)

SR = 44100


def tone(freqs, dur=0.2):
    t = np.arange(int(SR * dur)) / SR
    sig = sum(np.sin(2 * np.pi * f * t) for f in freqs)
    return (sig / len(freqs)).astype(np.float32)


def local_peaks(db, freqs, min_prominence_db=12.0):
    floor = db.max() - 40.0
    peaks = []
    for i in range(1, len(db) - 1):
        if db[i] > db[i - 1] and db[i] >= db[i + 1] and db[i] > floor:
            if db[i] - min(db[:i].min() if i else db[i], db[i + 1 :].min()) > min_prominence_db:
                peaks.append(freqs[i])
    return peaks


def main() -> int:
    freqs = column_frequencies(SR)
    res = SR / DEFAULT_FFT_SIZE
    print(f"fft_size={DEFAULT_FFT_SIZE}  resolution={res:.1f} Hz  bins={freqs.size}\n")

    # 1) Pure tone peaks at its frequency.
    db = spectrum_column(tone([440.0]), SR)
    peak_freq = freqs[int(np.argmax(db))]
    ok_tone = abs(peak_freq - 440.0) <= res
    print(f"[{'OK ' if ok_tone else 'FAIL'}] 440 Hz tone -> peak at {peak_freq:.1f} Hz")

    # 2) Two close tones resolve as two peaks (narrowband).
    db2 = spectrum_column(tone([300.0, 360.0]), SR)
    peaks = [f for f in local_peaks(db2, freqs) if 250 <= f <= 410]
    near300 = any(abs(p - 300) <= res for p in peaks)
    near360 = any(abs(p - 360) <= res for p in peaks)
    ok_resolve = near300 and near360
    print(f"[{'OK ' if ok_resolve else 'FAIL'}] 300+360 Hz -> peaks {np.round(peaks,1).tolist()} "
          f"(both resolved: {ok_resolve})")

    all_ok = ok_tone and ok_resolve
    print("\nRESULT:", "ALL PASS" if all_ok else "FAILURES PRESENT")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
