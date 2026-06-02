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
```

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
