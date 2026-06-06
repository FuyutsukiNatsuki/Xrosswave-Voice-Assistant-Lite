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
| 2026-06-02 | Claude Code (Opus 4.8) | 警告閾値をJitter10%/Shimmer15%に変更。フォルマントをチャンク毎(~21Hz)に高速化（カデンス分離）。入力ソース選択UI追加。**フェーズ2完了** |
| 2026-06-02 | Claude Code (Opus 4.8) | UX改善: グラフのマウスオーバーでカーソル位置のHzをクロスヘア表示。右上数値表示にF1〜F4を追加（F0と色分けで並列）。ユーザー確認: フォルマント精度~90%で良好、ソース切替/開始/停止も正常 |
| 2026-06-03 | Claude Code (Opus 4.8) | **フェーズ3**: エラー処理（起動失敗ダイアログ・worker堅牢化・`pipeline.error`）、性能実測（毎チャンク解析1.05ms/予算46ms＝2%）、**.exe化（PyInstaller）成功・起動確認**、最終ドキュメント整備。全検証スイート合格 |
| 2026-06-03 | Claude Code (Opus 4.8) | 配布調整: アプリアイコン生成(`make_icon.py`→`assets/icon.ico`)、ウィンドウ/exeに適用、単一ファイル(`-OneFile`)オプション追加。ユーザーの「DLL無し」エラーは`build\`を実行したのが原因（正解は`dist\`）と判明・案内 |
| 2026-06-03 | Claude Code (Opus 4.8) | GitHub公開準備: README/LICENSE(GPLv3)/.gitattributes/スクショ追加。**GitHubに公開**（GPLv3, public, main, gh CLI）。URL: github.com/FuyutsukiNatsuki/Xrosswave-Voice-Assistant-Lite。生声wav等の非公開も確認 |
| 2026-06-03 | Claude Code (Opus 4.8) | READMEにGoogle Drive配布セクション追加（SmartScreen注意含む） |
| 2026-06-03 | Claude Code (Opus 4.8) | **機能追加: 狭帯域スペクトログラム**（`analysis/spectrogram`＋`gui/spectrogram_plot`、FFT2048≒21.5Hz分解能、スクロール式ウォーターフォール、表示ON/OFF）。3ペインをQSplitterで配置。合成音で分解能検証・スモーク合格・スクショ更新 |
| 2026-06-03 | Claude Code (Opus 4.8) | ビルドスクリプトをcwd非依存に修正（PSScriptRoot基準、失敗時throw）。マイク入力デバイス選択ドロップダウン追加（`list_input_devices`、既定=システム既定、マイク選択時のみ表示） |
| 2026-06-03 | Claude Code (Opus 4.8) | ファイル再生機能追加: `FileInput`が出力デバイスへ再生（出力デバイス選択＋音量スライダー既定10%、ライブ調整）。pauseで再生も停止（pipeline→source.pause転送）。出力失敗時は無音フォールバック。スクショ更新 |
| 2026-06-03 | Claude Code (Opus 4.8) | フォルマント/SG表示を6400Hzへ拡張（Burg ceilingも6400）。広帯域SG追加（窓256）＋Viewメニューで4ペイン表示切替。ピッチ既定をNormalに。設定永続化(`config.py`, JSON, `XVALITE_CONFIG_DIR`で上書き可)。全検証合格・config往復確認 |

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
- [x] GUI の骨組み（`gui/main_window.MainWindow`、ソース選択UI=マイク/ファイル＋Browse、Start/Stop、Pause/Resume、Rangeレンジ切替。MainWindowがパイプライン生成・切替を管理。ファイル終端で自動停止）
- [x] リアルタイムピッチグラフ（スクロール式、`gui/scrolling_plot.ScrollingPlot`、最新タイムスタンプ基準でスクロール、無声=NaNギャップ）
- [x] リアルタイムフォルマントグラフ（スクロール式、F1〜F4の4系列＋マーカー、1秒周期、`ScrollingPlot`再利用）
- [x] Jitter/Shimmer 警告表示（声質パネル。閾値超過で赤＋⚠表示、無音時は--）
- [x] 一時停止機能（Pause/Resume → `pipeline.pause/resume`。停止中はグラフも凍結）

> **フェーズ2完了**（全要件＋追加機能を実装・検証）。今後の候補: 見た目調整、フォルマント精度の追い込み、F0平滑化など。

> GUI 検証方針: この環境では `smoke_gui.py`（offscreen で起動・pause/resume・データ受信を自動確認）で検証。実際の見た目は手元で `run_app.py` 実行が必要。

### フェーズ 3: 仕上げ
- [x] パフォーマンス計測（`bench_analysis.py`）: 毎チャンク解析 1.05ms / 予算46ms＝**2%**。十分な余裕、チューニング不要
- [x] エラー処理: 起動失敗（マイク無し/ファイル不正）はダイアログ表示しクラッシュせず（`smoke_errors.py`で検証）。worker堅牢化（ソースエラー→`pipeline.error`、解析エラー→チャンクスキップ）
- [x] .exe パッケージング（PyInstaller、`scripts/build_exe.ps1`）。ビルド成功・起動確認済み（`dist\XVALite\XVALite.exe`、配布フォルダ~196MB）
- [x] `CLAUDE.md` にビルド・実行・テスト・パッケージングコマンドと確定アーキテクチャを追記

> **フェーズ3完了 = 主要開発フェーズすべて完了。** 全検証スクリプト合格。今後の候補: アイコン/署名付きの配布調整、見た目テーマ、F0平滑化オプション、設定の永続化など。

## 引き継ぎ時の注意

- このファイルと `CLAUDE.md` は重複させず、役割を分ける:
  - `CLAUDE.md` = 恒久的なプロジェクト知識（アーキテクチャ・コマンド・規約）
  - `Handoff.md` = 流動的な作業状態（直近の進捗・未完了タスク・申し送り）
- 作業を引き継ぐ際は、まず「現在のリポジトリ状態」「直近の作業ログ」「次にやるべきこと」を確認してください。
- リアルタイム性能が最重要要件。設計・ライブラリ選定はこの観点を優先すること。
