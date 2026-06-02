# Handoff.md

このファイルは、AIエージェント間（Claude Code / Codex / Antigravity など）の引き継ぎ書です。
作業を行ったエージェントは、セッション終了時にこのファイルを更新してください。

---

## プロジェクト概要

- **名称**: XVALite
- **場所**: `C:\XVALite`
- **現状**: 設計フェーズ。要件は確定、コードは未着手。
- **種別**: ボイストレーニング支援ツール（デスクトップアプリ）
- **目的**: 歌唱・発声練習者が、自分の声のピッチ・フォルマント・声質（Jitter/Shimmer）をリアルタイムに可視化し、フィードバックを得られるようにする。

### 技術スタック

| 層 | 採用技術 |
|----|---------|
| バックエンド | Python |
| フロントエンド | Python ベースのローカル GUI |
| 音声解析 | Parselmouth（Praat の Python ラッパー） |

## 機能要件

| # | 機能 | 更新頻度 | 備考 |
|---|------|---------|------|
| 1 | ピッチ取得・表示 | リアルタイム | 現在のピッチ（F0）を数値/インジケータで表示 |
| 2 | ピッチグラフ軌跡 | リアルタイム | 左→右に軌跡が伸び、スクロールし、古い点は消える（スクロール式時系列グラフ） |
| 3 | フォルマント表示 | 準リアルタイム（1秒間隔） | F1〜F4 を1秒おきに分析・出力 |
| 4 | フォルマントグラフ軌跡 | リアルタイム更新 | ピッチグラフと同様のスクロール式時系列表示 |
| 5 | Jitter / Shimmer 検知 | 1秒間隔 | 値が閾値を超えたら警告表示 |
| 6 | 入力ソース切替 | — | マイク入力 / 音声ファイル入力の両対応 |
| 7 | グラフ一時停止 | — | 軌跡の更新を一時停止できる |

## アーキテクチャ方針（要設計）

リアルタイム性が要となるため、以下のスレッド/責務分離を想定:

- **音声入力スレッド** — マイク/ファイルから音声を一定サイズのチャンクで取得しキューへ投入
  - 候補ライブラリ: `sounddevice`（推奨） or `PyAudio`
- **解析層** — チャンクを受け取り Parselmouth で解析
  - ピッチ（F0）: 高頻度（フレームごと）
  - フォルマント / Jitter / Shimmer: 1秒間隔のウィンドウ単位
  - 重い解析が GUI をブロックしないよう、別スレッド/プロセスで実行
- **GUI / 描画層** — 解析結果を受け取りグラフを更新
  - スクロール式リアルタイムグラフには `pyqtgraph`（PySide6 / PyQt6 上）が高性能でほぼ唯一の現実解。matplotlib + Tkinter はリアルタイムスクロールには性能的に不向き。

### 確定済みの設計判断

- **一時停止の挙動**: 解析も描画も両方停止する。再開時は停止位置から続行（停止中の音声は解析しない）。
- **Jitter / Shimmer の警告閾値**: 固定値とする（ユーザー設定にはしない）。具体値はフェーズ1で決定。
- **ファイル入力時の挙動**: 実時間で再生しながら解析する（マイク入力と同じパイプラインを通し、リアルタイム表示と挙動を揃える）。
- **GUI フレームワーク**: PySide6 + pyqtgraph（スクロール式リアルタイムグラフの性能要件のため）。
- **音声入力ライブラリ**: sounddevice（マイク取得・ファイル再生の両方に使用）。

### 未決定の設計判断

（現時点でなし。新たに判断が必要になった項目はここに追記する）

## 現在のリポジトリ状態

- Python: **3.11.9**（既定の 3.14 は parselmouth/PySide6 の wheel 未対応のため不採用）
- 仮想環境: `C:\XVALite\.venv`（3.11.9）
- 依存管理: `requirements.txt`（インストール済み・疎通確認済み）
  - praat-parselmouth 0.4.7 / sounddevice 0.5.5 / soundfile 0.13.1 / numpy 2.4.6 / PySide6 6.11.1 / pyqtgraph 0.14.0
- Git リポジトリ: 初期化済み（`master`、初回コミット `8cfdca8`）
- 既存ファイル:
  - `CLAUDE.md` — Claude Code 向けのガイダンス
  - `Handoff.md` — このファイル
  - `requirements.txt` — 依存パッケージ
  - `.gitignore` — `.venv/`・音声ファイル・`.claude/settings.local.json` 等を除外

### 実行環境メモ
- venv の Python: `C:\XVALite\.venv\Scripts\python.exe`
- 入力デバイスは検出済み（Yamaha AG06MK2 等）。`sounddevice.query_devices()` で列挙可能。

### テストデータ
- `C:\XVALite\testdata\test.wav` — ユーザー提供の実声（母音 い/え/お/あ/う、44100 Hz / モノ / 6.59秒 / PCM_16）。
- `*.wav` は `.gitignore` 済み（個人音声はリポジトリに含めない＝他環境では別途配置が必要）。
- 用途: ファイル入力パイプラインの実データ検証 / フォルマントの母音別妥当性確認 / Jitter・Shimmer の実声レンジ確認。
- 検証コマンド: `scripts\verify_file_input.py`（整合性・ペーシング・1秒窓の全解析を一括実行）。

## 直近の作業ログ

| 日付 | エージェント | 作業内容 |
|------|------------|---------|
| 2026-06-02 | Claude Code (Opus 4.8) | `CLAUDE.md` と `Handoff.md` を新規作成 |
| 2026-06-02 | Claude Code (Opus 4.8) | アプリ要件をヒアリングし Handoff.md に概要・機能要件・アーキテクチャ方針を記述 |
| 2026-06-02 | Claude Code (Opus 4.8) | 全設計判断を確定。Python 3.11 venv 作成、依存インストール、import/デバイス疎通確認 |
| 2026-06-02 | Claude Code (Opus 4.8) | `.gitignore` 作成、Git 初期化・初回コミット（`8cfdca8`）。フェーズ0完了 |
| 2026-06-02 | Claude Code (Opus 4.8) | `src/xvalite` パッケージ作成。音声入力(`AudioInput`)とF0抽出(`pitch`)を実装、検証スクリプトで疎通確認（フェーズ1の前半完了） |
| 2026-06-02 | Claude Code (Opus 4.8) | フォルマント抽出(`analysis/formant`, Burg法)を実装。合成母音で F1〜F4 復元を検証（相対許容10%）。実機マイク用スクリプトも追加 |
| 2026-06-02 | Claude Code (Opus 4.8) | Jitter/Shimmer(`analysis/voice_quality`, PointProcess)を実装。固定閾値・VoiceQuality dataclass。合成音で揺らぎ有無を検証。残るはファイル入力接続のみ |
| 2026-06-02 | Claude Code (Opus 4.8) | ファイル入力(`audio/file_input.FileInput`)を実装。生声 test.wav で整合性・実時間ペーシング・全解析を検証。**フェーズ1完了** |
| 2026-06-02 | Claude Code (Opus 4.8) | 統合層(`pipeline.AnalysisPipeline`)を実装。2系統カデンス・結果ストリーム・一時停止セマンティクスを生声で検証。次はGUI |
| 2026-06-02 | Claude Code (Opus 4.8) | GUI最小版(`gui/`)実装: ScrollingPlot＋ピッチグラフ＋Pause/Stop＋QTimerドレイン。`run_app.py`起動、`smoke_gui.py`でoffscreen自動検証（17点描画・例外なし） |
| 2026-06-02 | Claude Code (Opus 4.8) | F0追跡＆表示上限を C7(≒2100Hz)に拡張（声エンスージアスト向け）。pipeline.pitch_floor/ceiling を公開しGUI軸と連動。トレードオフ: 高ceilingで遷移部にオクターブ誤検出が出やすい（平滑化は未実装） |
| 2026-06-02 | Claude Code (Opus 4.8) | 入力デッドゾーン(`silence_db`既定-40dBFS)追加。無音窓は解析せずNaN。実測（音声~-20/無音<-44dBFS）に基づき決定、偽フレーム20個除去を確認。`--silence-db`で調整可 |
| 2026-06-02 | Claude Code (Opus 4.8) | F0レンジ切替UI追加: 通常(≤880Hz/A5)↔拡張(≤2100Hz/C7)をドロップダウンで実行中切替（オクターブ跳ね対策）。フォルマントグラフ(F1〜F4)追加。smoke_guiで検証 |
| 2026-06-02 | Claude Code (Opus 4.8) | Jitter/Shimmer警告表示（声質パネル、閾値超過で赤＋⚠）。smoke_guiで更新を検証。フェーズ2の主要機能ほぼ完了 |

### 技術メモ: フォルマント分析の高速化余地
- 現状フォルマントとJitter/Shimmerは同じ1秒カデンス(`SlowSample`)に束ねている。1秒は要件上の選択で技術的限界ではない。
- フォルマントはチャンク周期（blocksize2048＝約46ms≒20Hz）まで短縮可能。窓は~25〜50msで足りる（Praat標準窓25ms）。実用域は窓~100〜200ms/更新~50ms。
- Jitter/Shimmerは複数声門周期が必要なため~300〜500ms未満は信頼性低下。1秒程度が妥当な下限。
- 高速化するなら両者を別カデンスに分離する設計変更が必要（フォルマント高速・声質1秒維持）。

## 次にやるべきこと（TODO）

### フェーズ 0: 環境準備
- [x] 上記「未決定の設計判断」をユーザーと確定する
- [x] Python 環境（venv 等）と依存管理ファイルを用意する
- [x] Parselmouth / 音声入力 / GUI ライブラリをインストールし疎通確認
- [x] Git リポジトリを初期化する

### フェーズ 1: 音声パイプライン（GUI なし）
- [x] マイクからのチャンク取得 → キュー投入を実装（`xvalite.audio.input.AudioInput`）
- [x] Parselmouth でピッチ（F0）を抽出（`xvalite.analysis.pitch`）。合成正弦波で誤差0.00 Hz・無音=NaN を確認。マイク実機でチャンク取得も確認済み
- [x] フォルマント（F1〜F4）を1秒ウィンドウで抽出（`xvalite.analysis.formant`、Burg法）。合成母音で F1〜F3 誤差約30 Hz以内・F4 も10%以内を確認
- [x] Jitter / Shimmer を1秒ウィンドウで算出（`xvalite.analysis.voice_quality`、PointProcess）。固定閾値（jitter>1.04% / shimmer>3.81%）。揺らぎ無し=0%・注入量3%/10%→測定3.22%/9.23%で検証
- [x] 音声ファイル入力を同パイプラインに接続（`xvalite.audio.file_input.FileInput`、soundfile、実時間ペース、終端=None）。生声 `testdata/test.wav` で整合性・ペーシング・全解析を確認

**→ フェーズ1完了。** 生声検証で母音 い/え/お/あ/う のフォルマント軌跡が音声学的に妥当（F1/F2 が母音ごとに想定どおり推移）、F0≈250 Hz 安定、Jitter<1%・Shimmer概ね閾値内を確認。

### フェーズ 2: GUI / 可視化
- [x] 統合層（`xvalite.pipeline.AnalysisPipeline`）— 入力源を抽象化し、F0=高頻度・フォルマント/Jitter=1秒周期でバックグラウンド解析。結果はFIFO(`drain`)＋最新スナップショットで供給。一時停止＝解析停止＆バッファクリア。サンプル数ベースの時刻。生声で全チェック合格（slow 6件/6.59秒、F0中央値250.7Hz、pause中0件→resume復帰）
- [~] GUI の骨組み（`gui/main_window.MainWindow`、Pause/Resume・Stop ボタン実装済み。**入力ソース選択UIは未**＝現状は `run_app.py --file` / 既定マイクで切替）
- [x] リアルタイムピッチグラフ（スクロール式、`gui/scrolling_plot.ScrollingPlot`、最新タイムスタンプ基準でスクロール、無声=NaNギャップ）
- [x] リアルタイムフォルマントグラフ（スクロール式、F1〜F4の4系列＋マーカー、1秒周期、`ScrollingPlot`再利用）
- [x] Jitter/Shimmer 警告表示（声質パネル。閾値超過で赤＋⚠表示、無音時は--）
- [x] 一時停止機能（Pause/Resume → `pipeline.pause/resume`。停止中はグラフも凍結）

> フェーズ2はほぼ完了。残るは「入力ソース選択UI」（現状CLI）と、必要なら見た目調整。

> GUI 検証方針: この環境では `smoke_gui.py`（offscreen で起動・pause/resume・データ受信を自動確認）で検証。実際の見た目は手元で `run_app.py` 実行が必要。

### フェーズ 3: 仕上げ
- [ ] パフォーマンスチューニング（描画フレームレート、解析負荷）
- [ ] エラー処理（デバイス無し、ファイル不正など）
- [ ] `CLAUDE.md` にビルド・実行・テストコマンドと確定アーキテクチャを追記

## 引き継ぎ時の注意

- このファイルと `CLAUDE.md` は重複させず、役割を分ける:
  - `CLAUDE.md` = 恒久的なプロジェクト知識（アーキテクチャ・コマンド・規約）
  - `Handoff.md` = 流動的な作業状態（直近の進捗・未完了タスク・申し送り）
- 作業を引き継ぐ際は、まず「現在のリポジトリ状態」「直近の作業ログ」「次にやるべきこと」を確認してください。
- リアルタイム性能が最重要要件。設計・ライブラリ選定はこの観点を優先すること。
