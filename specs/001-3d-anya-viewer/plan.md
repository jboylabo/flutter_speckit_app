# Implementation Plan: 3D アーニャビューア

**Branch**: `001-3d-anya-viewer` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-3d-anya-viewer/spec.md`

## Summary

1 枚のキャラクター画像から 3D の「立体スタンディ」モデル (glTF Binary) を生成し、
Flutter GPU ベースの `flutter_scene` でネイティブ描画する。ユーザーはドラッグ / ピンチで
自由に視点を変えられ、モデルに焼き込んだアニメーション (Spin / Bounce) を再生できる。

当初は `flutter_3d_controller` (WebView + model-viewer) で実装したが、WebView 依存が
iOS で CocoaPods フォールバックを引き起こすため、`flutter_scene` によるネイティブ描画へ切り替えた。

## Technical Context

**Language/Version**: Dart 3.13.2 / Flutter 3.47.2 (mise で固定)

**Primary Dependencies**: `flutter_scene` ^0.23.0 (Flutter GPU + Impeller), `vector_math` ^2.4.2、
モデル生成は Python 3 + Pillow (`tool/build_anya_model.py`)

**Storage**: N/A (アセットのみ)

**Testing**: `flutter test` (ウィジェットテスト)、`flutter analyze`、iOS シミュレータでの目視確認

**Target Platform**: iOS / Android (Flutter GPU を各プラットフォーム設定で有効化)

**Project Type**: モバイルアプリ (単一 Flutter プロジェクト)

**Performance Goals**: 60fps 相当でのカメラ操作追従、起動 3 秒以内の初期表示

**Constraints**: ネットワーク不要 (アセット同梱)、著作物をリポジトリに含めない、
3D 描画は Flutter GPU 有効化が前提

**Scale/Scope**: 1 画面、モデル 1 体、アニメーション 2 種

## Constitution Check

`.specify/memory/constitution.md` は未記入のテンプレートのままで、有効な原則が定義されていない。
そのため強制されるゲートは無い。憲法を定義したら本計画を再チェックすること。

## Project Structure

### Documentation (this feature)

```text
specs/001-3d-anya-viewer/
├── plan.md              # このファイル
├── spec.md              # 機能仕様
├── tasks.md             # タスク一覧
└── checklists/
    └── requirements.md  # 仕様品質チェックリスト
```

### Source Code (repository root)

```text
lib/
├── main.dart                          # アプリのエントリポイント
└── src/
    ├── pages/
    │   └── anya_viewer_page.dart      # Scene 構築 / 軌道カメラ / アニメーション制御
    └── widgets/
        └── anya_control_panel.dart    # 操作 UI (描画非依存 = テスト可能)

test/
└── widget_test.dart                   # 操作パネルのウィジェットテスト

tool/
└── build_anya_model.py                # 元画像 -> assets/anya/anya.glb 生成

hook/
└── build.dart                         # flutter_scene のアセット変換ビルドフック

assets/anya/                           # 生成物 (git 管理外)
flutter_scene_generated/               # ビルド時に生成される .fsceneb 等
```

**Structure Decision**: 単一 Flutter プロジェクト。描画状態を持つページと、描画に依存しない
プレゼンテーション用ウィジェットを分離し、後者をウィジェットテストの対象にする。

## Key Decisions

| 決定 | 理由 | 却下した代替案 |
|------|------|----------------|
| `flutter_scene` (Flutter GPU) で描画 | ネイティブ描画で WebView 不要。iOS のネイティブ依存が消え CocoaPods も不要になる | `flutter_3d_controller`: WebView 依存で `flutter_inappwebview` が SPM 未対応、CocoaPods が必要になる |
| 板 2 枚 + 台座の「立体スタンディ」 | 単一の 2D 画像からは立体メッシュを起こせないため | フル 3D メッシュ: 元素材が 1 枚絵しかなく作成不可 |
| モデルをスクリプトで生成 | 著作物をリポジトリに置かずに再現できる | glb を直接コミット: 公開リポジトリでの再配布になる |
| アニメーションを glTF に焼き込む | エンジン側の実装なしで再生 / 一時停止 / 停止が扱える | Dart 側で毎フレーム変換: 実装が増え、モデルと分離してしまう |

## Complexity Tracking

| 追加要素 | 必要な理由 | 単純案を採らなかった理由 |
|----------|-----------|--------------------------|
| `tool/build_anya_model.py` (glTF 生成器) | 元素材が PNG のみで、3D モデルが存在しない | 既製モデルの入手は権利面で不可、手作業の 3D 制作は本機能の範囲外 |
