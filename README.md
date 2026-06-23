# XVALite — Xrosswave Voice Assistant Lite

**声をリアルタイムに「見る」ボイストレーニング支援ツール。** マイクや音声ファイルから、
ピッチ・フォルマント・声質・スペクトルを同時に可視化します。歌や発声の練習、
母音・倍音・声質のチェックに。

主な可視化（すべて表示ON/OFFを切替可能）:

- 🎵 **ピッチ（F0）** — スクロール式グラフ＋数値（音名・セント併記、例 `B3 +38¢`）。通常/拡張(C7)レンジ切替
- 🗣️ **フォルマント（F1〜F4）** — スクロール式グラフ＋数値（〜6.4 kHz）
- 〰️ **オシロスコープ** — 入力波形（自動ゲインで小さい声も見やすい）
- 📈 **瞬時スペクトラム** — 対数軸（10 Hz〜10 kHz）のFFT、ピークホールド対応
- 🌈 **スペクトログラム（狭帯域／広帯域）** — スクロール式ウォーターフォール
- ⚠️ **声質（Jitter / Shimmer）** — 1秒ごとに算出し、閾値超過で警告
- 🧭 **母音・響き・声区・声の傾向の推定** — 母音、響きタイプ、地声/ミックス/裏声、男声寄り/中声/女声寄りを推定（目安）

数値・推定値は画面左の縦パネルにリスト表示、グラフは右側に縦積みで表示します。

> A real-time voice-training visualizer: live pitch (F0), formants (F1–F4),
> oscilloscope, instantaneous spectrum, narrow/wideband spectrograms, and
> jitter/shimmer — from microphone or audio-file input.

![XVALite のスクリーンショット](assets/screenshot.png)

## ダウンロード（配布版）

ビルド済みの実行ファイルを Google Drive で配布しています。**Python のインストールは不要**です（Windows 向け）。

📦 **[ダウンロード（Google Drive）](https://drive.google.com/drive/folders/1pettJwR26mmdZwlys07NzLINzFw2JFBS?usp=sharing)**

1. リンクからフォルダ（または zip）をダウンロードします。
2. zip の場合は展開し、`XVALite` フォルダを任意の場所に置きます。
3. フォルダ内の **`XVALite.exe`** をダブルクリックで起動します。
   - フォルダ版は `XVALite` フォルダごと必要です（中のファイルだけを動かさないでください）。
   - 単一ファイル版（`XVALite.exe` 1個）の場合はそのまま実行できます。

> **「WindowsによってPCが保護されました」と表示されたら:** 本アプリはコード署名をして
> いないため、初回起動時に SmartScreen の警告が出ることがあります。配布元が信頼できる
> 場合は **「詳細情報」→「実行」** で起動できます。

## 機能の詳細

### 可視化パネル

各パネルは **View メニュー**から個別に表示／非表示でき、境界をドラッグして高さを調整できます。

| パネル | 内容 |
|--------|------|
| ピッチ (F0) | 基本周波数をスクロール表示。無声・無音区間は線が途切れます。レンジは通常（≤880 Hz / A5）↔ 拡張（≤2100 Hz / C7）を実行中に切替 |
| フォルマント (F1–F4) | 第1〜第4フォルマントをスクロール表示（約21 Hz 更新、〜6.4 kHz）。母音の調音を確認 |
| オシロスコープ | 時間波形をリアルタイム表示。縦軸は信号に追従して自動ゲイン |
| 瞬時スペクトラム | 今この瞬間の周波数成分を対数軸（10 Hz〜10 kHz）の折れ線で表示。ピークホールド対応 |
| スペクトログラム（狭帯域） | 周波数分解能重視。倍音が横縞として見える |
| スペクトログラム（広帯域） | 時間分解能重視（狭帯域の約8倍）。フォルマント帯やピッチの立ち上がりが見える |

### 数値表示・声質・推定（左パネル）

画面左の縦パネルにリスト表示されます。

- **ピッチ・フォルマント** — F0・F1〜F4 の現在値を色分け表示。
- **声質** — Jitter / Shimmer（固定閾値 Jitter 10 % / Shimmer 15 % 超過で赤く警告）。
- **推定** — **母音**（あ/い/う/え/お）、**響きタイプ**（明るい・前寄り／バランス型／暗い・カバー／深い咽頭腔／鼻腔・トゥワング／息漏れ・かすれ）、**声区**（地声寄り／ミックス／裏声寄り）、**声の傾向**（男声寄り／中声／女声寄り）を確度付きで推定、HNR も表示。
  - 推定は F0・F1・HNR・スペクトル重心などから算出する**目安**です（断定ではありません）。マイクや個人差で変動し、持続発声で安定します。
  - “性別”の判定ではなく**声の音響的な傾向**を表します（声だけから性別は判定できないため）。ピッチのみで男女判定する手法とは異なり、フォルマント・HNR・スペクトルも併用しています。

### 入力・再生

- **入力ソース** — マイク（入力デバイス選択可）／音声ファイル。
- **ファイル再生** — 音声ファイルを実時間で再生しながら解析。**出力デバイス選択**＋**音量スライダー**（ライブ調整）。
- **一時停止** — 解析・描画（とファイル再生）をまとめて停止／再開。
- **簡易録音** — マイク入力を録音ボタンで保存（44.1 kHz / 24 bit / モノラル WAV、実行ファイル配下の `rec/YYYY-MM-DD-nnnn.wav`）。
- **分析レポート** — 「レポート」をオンにして解析→停止すると、別ウィンドウでレポートを表示。平均ピッチ／平均声質、声の傾向・声区・響きの**割合（円グラフ）**、**母音別フォルマント（F1×F2、男声/女声平均と比較）**をまとめ、PNG 出力も可能。

### 便利機能

- **日本語 / 英語切替** — 画面右上の言語ドロップダウンでいつでも切替（初回はシステム言語、設定に保存）。操作系と推定の表示語を翻訳（グラフのタイトル・軸は専門用語として英語のまま）。
- **ダークテーマ** — 視認性のため常にダークテーマで表示。
- **マウスオーバー** — グラフ上のカーソル位置の周波数（Hz）を表示。
- **入力デッドゾーン** — 設定レベル未満の入力を無音として扱い、ノイズからの誤検出を抑制。
- **設定の保存** — レンジ・音量・表示パネル・ピークホールド・入出力デバイスを保存し、次回起動時に復元（`%APPDATA%\XVALite\config.json`）。

## 使い方

1. **Source** でマイクか音声ファイルを選択（ファイルは **Browse…** で指定）。
2. マイクなら **Device**、ファイルなら **Output** デバイスと **Vol**（音量）を必要に応じて設定。
3. **Start** で解析開始。各パネルが左→右にスクロールします。
4. **View** メニューで見たいパネルを選択、**Range** でピッチ上限を切替、**Peak hold** でスペクトラムのピーク保持を切替。
5. **Pause** で一時停止／再開、**Stop** で停止。

## 動作環境

- Windows
- ソースから動かす場合: **Python 3.11**
  （Parselmouth / PySide6 が新しい Python の wheel を提供していないため 3.11 を使用）

## インストールと実行（ソースから）

```powershell
# リポジトリを取得
git clone https://github.com/FuyutsukiNatsuki/Xrosswave-Voice-Assistant-Lite.git
cd Xrosswave-Voice-Assistant-Lite

# 仮想環境を作成（Python 3.11）
py -3.11 -m venv .venv

# 依存をインストール
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 起動（マイク入力）
.\.venv\Scripts\python.exe scripts\run_app.py

# 音声ファイルを指定して起動
.\.venv\Scripts\python.exe scripts\run_app.py --file path\to\audio.wav
```

主なオプション: `--file PATH`（解析するファイル）, `--device N`（マイクのデバイス番号）,
`--silence-db DB`（入力デッドゾーン dBFS、既定 -40。0 に近づけるほど強くゲート）。

## 単体実行ファイル（.exe）のビルド

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# フォルダ版（推奨）→ dist\XVALite\XVALite.exe（XVALite フォルダごと配布）
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1

# 単一ファイル版 → dist\XVALite.exe
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -OneFile
```

> 実行可能な成果物は **`dist\`** にあります。`build\` は中間ファイル用で Python ランタイムを
> 含まないため、そこから実行すると「Failed to load Python DLL」エラーになります。

## アーキテクチャ概要

```
入力源 (AudioInput / FileInput)  ─ read() → 音声チャンク
        ▼
AnalysisPipeline（バックグラウンドスレッド）
   ├─ ピッチ (F0)        … チャンク毎
   ├─ フォルマント        … チャンク毎（約21 Hz）
   ├─ オシロ波形          … チャンク毎
   ├─ 瞬時スペクトラム＋狭帯域SG … チャンク毎
   ├─ 広帯域SG            … 約5.8 ms毎（高時間分解能）
   └─ Jitter/Shimmer・声区/声の傾向推定 … 1秒毎
        ▼
   結果ストリーム (drain) → GUI（PySide6 + pyqtgraph、複数パネル）
```

解析は別スレッドで動き、GUI は結果を受け取って描画するだけなので、重い解析が表示を
妨げません。音声解析は [Parselmouth](https://github.com/YannickJadoul/Parselmouth)（Praat）を使用。
詳細な設計・コマンドは [`CLAUDE.md`](CLAUDE.md)、開発経緯は [`Handoff.md`](Handoff.md) を参照してください。

## ライセンス

本プロジェクトは **GNU General Public License v3.0 (GPLv3)** で公開されています（全文は [`LICENSE`](LICENSE)）。
音声解析に用いている **Parselmouth（Praat）が GPLv3** のため、本プロジェクトも GPLv3 としています。
利用・改変・再配布の際は GPLv3 の条件に従ってください。

## 使用しているオープンソース

| ライブラリ | 用途 | ライセンス |
|-----------|------|-----------|
| [Parselmouth](https://github.com/YannickJadoul/Parselmouth) / [Praat](https://www.praat.org/) | 音声解析（F0・フォルマント・Jitter/Shimmer） | GPLv3 |
| [PySide6](https://doc.qt.io/qtforpython/) | GUI | LGPLv3 |
| [pyqtgraph](https://www.pyqtgraph.org/) | リアルタイムグラフ | MIT |
| [NumPy](https://numpy.org/) | 数値計算 | BSD |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | 音声入出力 | MIT |
| [soundfile](https://python-soundfile.readthedocs.io/) | 音声ファイル読み込み | BSD |
