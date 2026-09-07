import 'package:flutter/material.dart';

/// カメラのプリセット位置 (水平角 / 仰角はラジアン、距離はワールド単位)。
enum CameraPreset {
  front('正面', 0.0, 0.12, 3.6),
  // 1 枚絵から作ったスタンディなので真横はほぼ厚みだけになる。
  // 立体感が分かる斜め視点をプリセットにする。
  angled('斜め', 0.85, 0.18, 3.6),
  overhead('俯瞰', 0.35, 0.85, 3.9),
  closeUp('アップ', 0.0, 0.05, 2.1);

  const CameraPreset(this.label, this.yaw, this.pitch, this.distance);

  final String label;
  final double yaw;
  final double pitch;
  final double distance;
}

/// 3D ビューの操作パネル。描画に依存しないので単体でテストできる。
class AnyaControlPanel extends StatelessWidget {
  const AnyaControlPanel({
    super.key,
    required this.animations,
    required this.selectedAnimation,
    required this.isAnimationPlaying,
    required this.isAutoRotating,
    required this.onAnimationSelected,
    required this.onPlayPausePressed,
    required this.onStopPressed,
    required this.onAutoRotateChanged,
    required this.onPresetSelected,
  });

  final List<String> animations;
  final String? selectedAnimation;
  final bool isAnimationPlaying;
  final bool isAutoRotating;
  final ValueChanged<String?> onAnimationSelected;
  final VoidCallback onPlayPausePressed;
  final VoidCallback onStopPressed;
  final ValueChanged<bool> onAutoRotateChanged;
  final ValueChanged<CameraPreset> onPresetSelected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasAnimations = animations.isNotEmpty;

    return Material(
      color: theme.colorScheme.surfaceContainerHighest,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('カメラ', style: theme.textTheme.labelLarge),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (final preset in CameraPreset.values)
                    ActionChip(
                      label: Text(preset.label),
                      onPressed: () => onPresetSelected(preset),
                    ),
                ],
              ),
              const Divider(height: 24),
              Text('アニメーション', style: theme.textTheme.labelLarge),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        isDense: true,
                      ),
                      child: DropdownButton<String>(
                        value: selectedAnimation,
                        isExpanded: true,
                        underline: const SizedBox.shrink(),
                        hint: const Text('アニメーションなし'),
                        items: [
                          for (final animation in animations)
                            DropdownMenuItem<String>(
                              value: animation,
                              child: Text(animation),
                            ),
                        ],
                        onChanged: hasAnimations ? onAnimationSelected : null,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filledTonal(
                    tooltip: isAnimationPlaying ? '一時停止' : '再生',
                    onPressed: hasAnimations ? onPlayPausePressed : null,
                    icon: Icon(
                      isAnimationPlaying ? Icons.pause : Icons.play_arrow,
                    ),
                  ),
                  IconButton.filledTonal(
                    tooltip: '停止',
                    onPressed: hasAnimations ? onStopPressed : null,
                    icon: const Icon(Icons.stop),
                  ),
                ],
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('自動回転'),
                value: isAutoRotating,
                onChanged: onAutoRotateChanged,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
