---
description: "Task list for 3D アーニャビューア"
---

# Tasks: 3D アーニャビューア

**Input**: Design documents from `/specs/001-3d-anya-viewer/`

**Prerequisites**: plan.md, spec.md

**Tests**: 操作 UI に対するウィジェットテストのみ実施 (3D 描画はシミュレータでの目視確認)

**Organization**: ユーザーストーリー単位で分割し、各ストーリーを独立して実装 / 検証できるようにする

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並行実行可能 (別ファイル・依存なし)
- **[Story]**: 対応するユーザーストーリー (US1 / US2 / US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 依存とツールチェーンの用意

- [x] T001 `flutter_scene` と `vector_math` を `pubspec.yaml` に追加する
- [x] T002 `dart run flutter_scene:init` でアセットパイプライン (`hook/build.dart`、`flutter_scene_generated/`) を用意する
- [x] T003 [P] iOS の Flutter GPU を有効化する (`ios/Runner/Info.plist` に `FLTEnableFlutterGPU`)
- [x] T004 [P] Android の Flutter GPU を有効化する (`android/app/src/main/AndroidManifest.xml` の meta-data)
- [x] T005 [P] `mise.toml` を SPM 前提に整理し、Java を 21 LTS に固定する

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ストーリーが依存する 3D アセットの生成

**⚠️ CRITICAL**: モデルが無いとどのストーリーも成立しない

- [x] T006 元画像を取得し、透明部分をトリミングしてテクスチャ化する処理を `tool/build_anya_model.py` に実装する
- [x] T007 板 2 枚 (表 / 裏) + 台座シリンダーのジオメトリを生成する処理を `tool/build_anya_model.py` に実装する
- [x] T008 テクスチャを埋め込んだ glTF Binary (`assets/anya/anya.glb`) を出力する処理を `tool/build_anya_model.py` に実装する
- [x] T009 著作物と派生モデルを公開リポジトリに含めないよう `.gitignore` に `/assets/anya/` を追加する

**Checkpoint**: `python3 tool/build_anya_model.py` でモデルが生成でき、ユーザーストーリーに着手できる

---

## Phase 3: User Story 1 - 3D アーニャを表示して自由に眺める (Priority: P1) 🎯 MVP

**Goal**: 起動するとアーニャが 3D で表示され、ドラッグ / ピンチで自由に見られる

**Independent Test**: アプリを起動してモデルが描画され、ドラッグで角度が、ピンチで大きさが変わること

- [x] T010 [US1] `Scene.initializeStaticResources()` 完了後に `loadScene` でモデルを読み込む処理を `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T011 [US1] `SceneView` と軌道カメラ (`cameraBuilder`) を `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T012 [US1] ドラッグで回転・ピンチで距離を変える `GestureDetector` を `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T013 [US1] 読み込み中インジケータと、失敗時のエラー表示 / 再試行 UI を `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T014 [US1] アプリのエントリポイントとテーマを `lib/main.dart` に実装する

**Checkpoint**: MVP 完成 (3D アーニャを見て回せる)

---

## Phase 4: User Story 2 - アニメーションを再生する (Priority: P2)

**Goal**: モデルに焼き込んだアニメーションを選んで再生 / 一時停止 / 停止できる

**Independent Test**: 一覧に Spin / Bounce が出て、再生でモデルが動き、停止で初期姿勢に戻ること

- [x] T015 [US2] Spin (回転) / Bounce (跳ねる) アニメーションを glTF に焼き込む処理を `tool/build_anya_model.py` に実装する
- [x] T016 [US2] `parsedAnimations` から `AnimationClip` を作成し名前で引けるようにする処理を `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T017 [US2] 再生 / 一時停止 / 停止の操作を `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T018 [P] [US2] アニメーション選択と再生操作の UI を `lib/src/widgets/anya_control_panel.dart` に実装する

---

## Phase 5: User Story 3 - 視点をワンタップで切り替える (Priority: P3)

**Goal**: プリセット視点への切り替え、初期視点へのリセット、自動回転ができる

**Independent Test**: 各プリセットで視点が変わり、リセットで正面に戻り、自動回転で回り続けること

- [x] T019 [US3] カメラプリセット (正面 / 斜め / 俯瞰 / アップ) を `lib/src/widgets/anya_control_panel.dart` に定義する
- [x] T020 [US3] プリセット適用と正面へのリセットを `lib/src/pages/anya_viewer_page.dart` に実装する
- [x] T021 [US3] 自動回転のオン / オフを `lib/src/pages/anya_viewer_page.dart` に実装する

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T022 [P] 操作パネルのウィジェットテストを `test/widget_test.dart` に実装する
- [x] T023 [P] `flutter analyze` の警告をゼロにする
- [x] T024 iOS シミュレータでビルド・起動し、描画と 3D 回転を目視 / 差分で検証する
- [ ] T025 Android 実機またはエミュレータで描画を確認する
- [ ] T026 セットアップ手順 (モデル生成コマンド、Flutter GPU 有効化) を `README.md` に追記する

---

## Dependencies & Execution Order

- Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (Polish)
- US1 は単独で MVP として成立する
- US2 は T015 (モデル側のアニメーション) に依存する
- US3 は US1 のカメラ実装に依存する

## Parallel Opportunities

- T003 / T004 / T005: プラットフォーム設定とツールチェーン設定は別ファイルなので並行可能
- T018 と T016-T017: UI (パネル) と状態管理 (ページ) は別ファイルなので並行可能
- T022 / T023: テストと静的解析は独立

## Implementation Strategy

1. **MVP**: Phase 1-3 まで (3D アーニャが表示され、指で回せる)
2. **増分 1**: Phase 4 でアニメーション再生を追加
3. **増分 2**: Phase 5 で視点プリセットと自動回転を追加
4. **仕上げ**: Phase 6 でテスト・検証・ドキュメント
