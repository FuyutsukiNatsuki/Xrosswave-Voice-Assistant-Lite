# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

XVALite — a voice-training (ボイトレ) support desktop app. It visualizes the user's voice in real time: pitch (F0), formants (F1–F4), and voice-quality metrics (Jitter/Shimmer), from either microphone or audio-file input.

See `Handoff.md` for current work status, design decisions, and the phased TODO list. Keep `Handoff.md` updated (fluid work state); keep this file for durable knowledge (architecture, commands, conventions).

## Stack

- **Python 3.11** (NOT the system default 3.14 — parselmouth/PySide6 lack 3.14 wheels)
- Audio analysis: praat-parselmouth
- Audio I/O: sounddevice + soundfile
- GUI + realtime plotting: PySide6 + pyqtgraph
- Numerics: numpy

## Commands

The venv lives at `.venv` (Python 3.11.9). Use its interpreter directly:

```powershell
# Run anything with the project interpreter
& "C:\XVALite\.venv\Scripts\python.exe" <script.py>

# Install / update deps
& "C:\XVALite\.venv\Scripts\python.exe" -m pip install -r requirements.txt

# List audio input devices
& "C:\XVALite\.venv\Scripts\python.exe" -c "import sounddevice; print(sounddevice.query_devices())"

# Verify F0 extraction (deterministic, no mic needed)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_pitch_synthetic.py

# Live mic F0 readout
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_pitch_mic.py

# Verify formant extraction (deterministic, no mic needed)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_formant_synthetic.py

# Live mic formant readout
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_formant_mic.py

# Verify jitter/shimmer (deterministic, no mic needed)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_voice_quality_synthetic.py

# Verify narrowband spectrogram (deterministic, no mic needed)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_spectrogram_synthetic.py

# Live mic jitter/shimmer readout
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_voice_quality_mic.py

# Verify file input + full analysis on a recording (defaults to testdata\test.wav)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_file_input.py [path.wav]

# Verify the integration pipeline (throughput + pause semantics)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\verify_pipeline.py [path.wav]

# Launch the GUI (mic by default; --file for a recording)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\run_app.py --file testdata\test.wav

# Headless GUI smoke test (offscreen)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\smoke_gui.py

# Headless error-path smoke test (bad file → dialog, no crash)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\smoke_errors.py

# Benchmark per-chunk analysis cost vs the real-time budget
& "C:\XVALite\.venv\Scripts\python.exe" scripts\bench_analysis.py
```

## Packaging (.exe)

```powershell
# One-time: install build deps
& "C:\XVALite\.venv\Scripts\python.exe" -m pip install -r requirements-dev.txt

# Build → dist\XVALite\XVALite.exe (one-dir; ship the whole XVALite folder, ~196 MB)
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1

# Single-file build → dist\XVALite.exe (slower first start)
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -OneFile

# Regenerate the app icon (assets/icon.ico)
& "C:\XVALite\.venv\Scripts\python.exe" scripts\make_icon.py
```

The runnable output is in **dist\**, not build\ (build\ holds intermediate files
and has no python3xx.dll — running it gives "Failed to load Python DLL").

`xvalite_app.py` is the frozen entry point; `src/xvalite/app.py:main` is the shared
launch logic (dev launcher and exe both call it) and sets the window icon
(`assets/icon.ico`, resolved via `sys._MEIPASS` when frozen). The build embeds the
icon, bundles it as data, and collects soundfile / sounddevice / parselmouth
binaries (libsndfile, PortAudio, the Praat extension). Verified to launch;
~1 ms/chunk analysis vs a 46 ms budget (2%), so real time is comfortable.

## Layout

- `src/xvalite/` — the package (src layout). Verification scripts add `src/` to
  `sys.path` via `scripts/_bootstrap.py`; no editable install yet.
  - `app.py` — `main()`: builds the QApplication + MainWindow (shared by dev launcher and exe).
  - `audio/input.py` — `AudioInput`: sounddevice stream → thread-safe queue of mono float32 chunks.
  - `audio/file_input.py` — `FileInput`: file → same queue contract, real-time paced, `None` sentinel at EOF.
    Optional playback (`play`, `output_device`, live `volume`); a blocking output write paces the
    stream; `pause`/`resume` freeze playback+analysis. Output open failure → silent fallback (`play_error`).
  - `analysis/pitch.py` — `extract_f0` / `latest_f0`: Parselmouth F0 (unvoiced → NaN).
  - `analysis/formant.py` — `extract_formants` / `latest_formants`: Burg F1-F4 (undefined → NaN).
  - `analysis/voice_quality.py` — `measure_voice_quality` → `VoiceQuality` (local jitter/shimmer + fixed-threshold warning flags).
  - `analysis/spectrogram.py` — `spectrum_column` / `column_frequencies`: narrowband dB column (Hann + rFFT, fft_size 2048 ≈ 21.5 Hz resolution).
  - `pipeline.py` — `AnalysisPipeline`: ties a source to the analysis layer on a
    background thread. Cadences: F0 per chunk, formants per chunk (~21 Hz), narrowband
    spectrogram per chunk, jitter/shimmer once/sec (needs many glottal cycles). Results
    via `drain()` (FIFO of `PitchSample`/`FormantSample`/`VoiceQualitySample`/
    `SpectrogramColumn`) and `latest_pitch()`/
    `latest_formant()`/`latest_voice_quality()`. Start-time source failures raise out of
    `start()`; mid-stream source failures set `pipeline.error` and finish; per-chunk
    analysis errors skip that chunk.
    `pause()`/`resume()` halt analysis and discard audio. Timestamps are sample-count based.
    F0 tracked up to `pitch_ceiling` (default 2100 Hz ≈ C7, for high singing) — exposed
    as `pipeline.pitch_floor`/`pitch_ceiling` so the GUI axis matches. Trade-off: a high
    ceiling can yield occasional octave-jump spikes on noisy/transitional frames (no
    smoothing yet). Voice-quality periodicity keeps its own conservative ceiling.
    Input dead zone: windows quieter than `silence_db` (default -40 dBFS) emit NaN
    instead of inventing pitch/formants from the noise floor (speech ~-20 dBFS, silent
    gaps <-44 dBFS). Tunable via `pipeline.silence_db` or `run_app.py --silence-db`.
  - `gui/scrolling_plot.py` — `ScrollingPlot`: reusable pyqtgraph time-series widget;
    multiple named series, view scrolls by latest data timestamp, NaN → gaps. Hover
    crosshair shows the Hz at the cursor.
  - `gui/spectrogram_plot.py` — `SpectrogramPlot`: scrolling waterfall (ImageItem +
    inferno colormap); 2-D dB buffer scrolls left, levels auto-track the peak.
  - `gui/main_window.py` — `MainWindow`: owns the pipeline lifecycle. Source row
    (Microphone + input-device dropdown / Audio file + Browse… + output-device dropdown +
    volume slider) → Start builds source+pipeline; QTimer polls
    `pipeline.drain()` → pitch plot (F0) + formant plot (F1–F4, markers); Pause/Resume →
    `pipeline.pause/resume`; Range dropdown toggles F0 ceiling Normal (880 Hz/A5) ↔
    Extended (2100 Hz/C7) live. Numeric readout shows F0 + F1–F4 (color-matched).
    Voice-quality panel shows jitter/shimmer, red with ⚠ above the fixed thresholds
    (NaN/silence → "--"). File end auto-stops the controls.
- `scripts/` — runnable verification/smoke scripts (not part of the package).
  - `run_app.py` — launch the GUI (`--file PATH` for file input, else mic).
  - `smoke_gui.py` — headless (offscreen) GUI check; the visual run needs a real machine.

## Notes / gotchas

- **Formant analyzer pole budget**: `to_formant_burg` allocates `2 * num_formants`
  LPC poles up to `maximum_formant`. If `num_formants` exceeds the formants
  actually present, spare poles latch onto spurious peaks. The synthetic
  verifier matches the analyzer to its 4-formant signal (`num=4`, ceiling 4500);
  production defaults to 5 formants up to 5500 Hz for real voices.
- Formant accuracy degrades with frequency (a few % is normal), so the verifier
  uses a relative tolerance (max of 150 Hz and 10%), not a flat Hz bound.

## Architecture (planned)

Realtime performance is the top constraint. Three separated responsibilities:

1. **Audio input thread** — pull fixed-size chunks from mic/file (sounddevice) into a queue.
2. **Analysis layer** — Parselmouth on chunks. Pitch (F0) at high frequency; formants + Jitter/Shimmer on 1-second windows. Runs off the GUI thread so heavy analysis never blocks rendering.
3. **GUI / rendering layer** — PySide6 window + pyqtgraph scrolling plots fed from analysis results.

Key behaviors:
- Pitch & formant graphs scroll left→right; old samples drop off.
- Pause stops **both** analysis and rendering (audio during pause is not analyzed); resume continues from the stop point.
- File input plays in real time through the **same pipeline** as mic input.
- Jitter/Shimmer use **fixed** warning thresholds (not user-configurable).
