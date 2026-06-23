"""Minimal in-app internationalization (Japanese / English).

UI controls and estimation display terms are translated; plot titles/axis
labels stay English (technical terms), and vowel/note names are language-neutral.

Usage: ``set_language("en")`` then ``tr("start")``. The current language is a
module global so widgets can call ``tr`` at build/retranslate time.
"""

from __future__ import annotations

LANGUAGES = {"ja": "日本語", "en": "English"}
_DEFAULT = "ja"
_lang = _DEFAULT

_STRINGS = {
    # source row
    "source": {"ja": "ソース:", "en": "Source:"},
    "mic": {"ja": "マイク", "en": "Microphone"},
    "file": {"ja": "音声ファイル", "en": "Audio file"},
    "device": {"ja": "デバイス:", "en": "Device:"},
    "browse": {"ja": "参照…", "en": "Browse…"},
    "no_file": {"ja": "(ファイル未選択)", "en": "(no file selected)"},
    "default_device": {"ja": "既定（システム）", "en": "Default (system)"},
    "output": {"ja": "出力:", "en": "Output:"},
    "vol": {"ja": "音量:", "en": "Vol:"},
    # controls row
    "start": {"ja": "開始", "en": "Start"},
    "stop": {"ja": "停止", "en": "Stop"},
    "pause": {"ja": "一時停止", "en": "Pause"},
    "resume": {"ja": "再開", "en": "Resume"},
    "range": {"ja": "レンジ:", "en": "Range:"},
    "range_normal": {"ja": "通常（≤880 Hz）", "en": "Normal (≤880 Hz)"},
    "range_extended": {"ja": "拡張（≤2100 Hz, C7）", "en": "Extended (≤2100 Hz, C7)"},
    "peak_hold": {"ja": "ピークホールド", "en": "Peak hold"},
    "language": {"ja": "言語:", "en": "Language:"},
    "menu_view": {"ja": "表示", "en": "View"},
    # left panel headers
    "hdr_pitch_formant": {"ja": "ピッチ・フォルマント", "en": "Pitch & formants"},
    "hdr_quality": {"ja": "声質", "en": "Voice quality"},
    "hdr_estimate": {"ja": "推定", "en": "Estimation"},
    "register": {"ja": "声区", "en": "Register"},
    "tendency": {"ja": "声の傾向", "en": "Voice tendency"},
    "conf": {"ja": "確度", "en": "conf"},
    # register values
    "register.Chest": {"ja": "地声寄り", "en": "Chest"},
    "register.Mix": {"ja": "ミックス", "en": "Mix"},
    "register.Head": {"ja": "裏声寄り", "en": "Head/Falsetto"},
    # voice-tendency values
    "tendency.low": {"ja": "男声寄り", "en": "Male-leaning"},
    "tendency.mid": {"ja": "中声", "en": "Neutral"},
    "tendency.high": {"ja": "女声寄り", "en": "Female-leaning"},
    # confidence values
    "conf.high": {"ja": "高", "en": "High"},
    "conf.medium": {"ja": "中", "en": "Med"},
    "conf.low": {"ja": "低", "en": "Low"},
}


def set_language(lang: str) -> None:
    global _lang
    if lang in LANGUAGES:
        _lang = lang


def get_language() -> str:
    return _lang


def tr(key: str) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(_lang, entry.get(_DEFAULT, key))
