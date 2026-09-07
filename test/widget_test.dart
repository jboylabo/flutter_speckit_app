// 操作パネルのウィジェットテスト。
// 3D ビューア本体は WebView (プラットフォームビュー) を使うためテスト対象から外し、
// UI のロジックだけを検証する。

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_speckit_app/src/widgets/anya_control_panel.dart';

void main() {
  Widget wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

  testWidgets('アニメーションが無いときは再生ボタンが無効になる', (tester) async {
    await tester.pumpWidget(
      wrap(
        AnyaControlPanel(
          animations: const [],
          selectedAnimation: null,
          isAnimationPlaying: false,
          isAutoRotating: false,
          onAnimationSelected: (_) {},
          onPlayPausePressed: () {},
          onStopPressed: () {},
          onAutoRotateChanged: (_) {},
          onPresetSelected: (_) {},
        ),
      ),
    );

    expect(find.text('アニメーションなし'), findsOneWidget);
    final playButton = tester.widget<IconButton>(
      find.ancestor(
        of: find.byIcon(Icons.play_arrow),
        matching: find.byType(IconButton),
      ),
    );
    expect(playButton.onPressed, isNull);
  });

  testWidgets('カメラプリセットを押すとコールバックが呼ばれる', (tester) async {
    CameraPreset? tapped;

    await tester.pumpWidget(
      wrap(
        AnyaControlPanel(
          animations: const ['Spin', 'Bounce'],
          selectedAnimation: 'Spin',
          isAnimationPlaying: false,
          isAutoRotating: false,
          onAnimationSelected: (_) {},
          onPlayPausePressed: () {},
          onStopPressed: () {},
          onAutoRotateChanged: (_) {},
          onPresetSelected: (preset) => tapped = preset,
        ),
      ),
    );

    await tester.tap(find.text('俯瞰'));
    await tester.pump();

    expect(tapped, CameraPreset.overhead);
  });

  testWidgets('再生中は一時停止アイコンを表示し、自動回転を切り替えられる', (tester) async {
    bool? autoRotate;

    await tester.pumpWidget(
      wrap(
        AnyaControlPanel(
          animations: const ['Spin', 'Bounce'],
          selectedAnimation: 'Spin',
          isAnimationPlaying: true,
          isAutoRotating: false,
          onAnimationSelected: (_) {},
          onPlayPausePressed: () {},
          onStopPressed: () {},
          onAutoRotateChanged: (value) => autoRotate = value,
          onPresetSelected: (_) {},
        ),
      ),
    );

    expect(find.byIcon(Icons.pause), findsOneWidget);
    expect(find.byIcon(Icons.play_arrow), findsNothing);

    await tester.tap(find.byType(Switch));
    await tester.pump();

    expect(autoRotate, isTrue);
  });
}
