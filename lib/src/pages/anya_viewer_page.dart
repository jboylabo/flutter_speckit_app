import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_scene/scene.dart';
import 'package:vector_math/vector_math.dart' as vm;

import '../widgets/anya_control_panel.dart';

/// 3D モデルのアセットパス (ビルド時に flutter_scene の build hook が変換する)。
/// 実体は `python3 tool/build_anya_model.py` で生成する (リポジトリには含めない)。
const String kAnyaModelAsset = 'assets/anya/anya.glb';

/// カメラが注視する高さ。モデルは足元が y=0、頭が y=2.0。
final vm.Vector3 _kCameraTarget = vm.Vector3(0, 1.05, 0);

/// 3D アーニャを表示・操作する画面。
class AnyaViewerPage extends StatefulWidget {
  const AnyaViewerPage({super.key});

  @override
  State<AnyaViewerPage> createState() => _AnyaViewerPageState();
}

class _AnyaViewerPageState extends State<AnyaViewerPage> {
  final Scene _scene = Scene();
  final Map<String, AnimationClip> _clips = {};

  bool _isReady = false;
  String? _error;

  List<String> _animations = const [];
  String? _selectedAnimation;
  bool _isAnimationPlaying = false;
  bool _isAutoRotating = true; // TEMP verification

  // 軌道カメラの状態。毎フレーム cameraBuilder から読むので setState は不要。
  double _yaw = CameraPreset.front.yaw;
  double _pitch = CameraPreset.front.pitch;
  double _distance = CameraPreset.front.distance;
  double _distanceAtGestureStart = CameraPreset.front.distance;
  double _lastElapsedSeconds = 0;

  @override
  void initState() {
    super.initState();
    _loadModel();
  }

  Future<void> _loadModel() async {
    try {
      // 描画リソースの初期化が終わるまでは Scene に触らない。
      await Scene.initializeStaticResources();
      final anya = await loadScene(kAnyaModelAsset);
      _scene.add(anya);

      for (final animation in anya.parsedAnimations) {
        _clips[animation.name] = anya.createAnimationClip(animation)
          ..loop = true;
      }

      if (!mounted) {
        return;
      }
      setState(() {
        _isReady = true;
        _error = null;
        _animations = _clips.keys.toList(growable: false);
        _selectedAnimation =
            _animations.isNotEmpty ? _animations.first : null;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = '$error';
        _isReady = false;
      });
    }
  }

  void _retry() {
    setState(() {
      _error = null;
      _isReady = false;
      _clips.clear();
      _animations = const [];
      _selectedAnimation = null;
      _isAnimationPlaying = false;
      _isAutoRotating = false;
    });
    _loadModel();
  }

  Camera _buildCamera(Duration elapsed) {
    final seconds = elapsed.inMicroseconds / Duration.microsecondsPerSecond;
    final delta = (seconds - _lastElapsedSeconds).clamp(0.0, 0.1);
    _lastElapsedSeconds = seconds;

    if (_isAutoRotating) {
      _yaw += delta * 0.6;
    }

    // glTF モデルはインポート後 -Z を向くので、yaw=0 が正面になる。
    final horizontal = _distance * math.cos(_pitch);
    final position = vm.Vector3(
      horizontal * math.sin(_yaw),
      _kCameraTarget.y + _distance * math.sin(_pitch),
      -horizontal * math.cos(_yaw),
    );
    return PerspectiveCamera(position: position, target: _kCameraTarget);
  }

  void _handleScaleStart(ScaleStartDetails details) {
    _distanceAtGestureStart = _distance;
  }

  void _handleScaleUpdate(ScaleUpdateDetails details) {
    if (details.pointerCount > 1) {
      _distance = (_distanceAtGestureStart / details.scale).clamp(1.4, 12.0);
    }
    final drag = details.focalPointDelta;
    _yaw -= drag.dx * 0.008;
    _pitch = (_pitch + drag.dy * 0.006).clamp(-0.5, 1.3);
  }

  void _applyPreset(CameraPreset preset) {
    _yaw = preset.yaw;
    _pitch = preset.pitch;
    _distance = preset.distance;
  }

  void _selectAnimation(String? animation) {
    for (final clip in _clips.values) {
      clip.stop();
    }
    setState(() {
      _selectedAnimation = animation;
      _isAnimationPlaying = false;
    });
  }

  void _togglePlayPause() {
    final clip = _clips[_selectedAnimation];
    if (clip == null) {
      return;
    }
    if (_isAnimationPlaying) {
      clip.pause();
    } else {
      clip.play();
    }
    setState(() => _isAnimationPlaying = !_isAnimationPlaying);
  }

  void _stopAnimation() {
    _clips[_selectedAnimation]?.stop();
    setState(() => _isAnimationPlaying = false);
  }

  void _toggleAutoRotate(bool value) {
    setState(() => _isAutoRotating = value);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('3D アーニャ'),
        actions: [
          IconButton(
            tooltip: 'カメラをリセット',
            onPressed:
                _isReady ? () => _applyPreset(CameraPreset.front) : null,
            icon: const Icon(Icons.center_focus_strong),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(child: _buildViewerArea()),
          AnyaControlPanel(
            animations: _animations,
            selectedAnimation: _selectedAnimation,
            isAnimationPlaying: _isAnimationPlaying,
            isAutoRotating: _isAutoRotating,
            onAnimationSelected: _selectAnimation,
            onPlayPausePressed: _togglePlayPause,
            onStopPressed: _stopAnimation,
            onAutoRotateChanged: _toggleAutoRotate,
            onPresetSelected: _applyPreset,
          ),
        ],
      ),
    );
  }

  Widget _buildViewerArea() {
    final error = _error;
    if (error != null) {
      return _ModelErrorView(message: error, onRetry: _retry);
    }
    if (!_isReady) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('アーニャを読み込み中…'),
          ],
        ),
      );
    }

    return GestureDetector(
      onScaleStart: _handleScaleStart,
      onScaleUpdate: _handleScaleUpdate,
      child: SceneView(_scene, cameraBuilder: _buildCamera),
    );
  }
}

class _ModelErrorView extends StatelessWidget {
  const _ModelErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48),
          const SizedBox(height: 16),
          const Text(
            'モデルを読み込めませんでした',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            '$kAnyaModelAsset が見つからない場合は\n'
            '`python3 tool/build_anya_model.py` を実行してください。\n\n'
            '$message',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('再読み込み'),
          ),
        ],
      ),
    );
  }
}
