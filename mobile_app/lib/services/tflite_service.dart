import 'dart:typed_data';
import 'dart:ui';
import 'package:flutter/foundation.dart';
import 'package:tflite_flutter/tflite_flutter.dart';
import 'package:image/image.dart' as img;
import '../core/constants.dart';

// ─── Detection Model ──────────────────────────────────────────────────────────

class Detection {
  final Rect bbox;
  final String label;
  final double confidence;
  double? thermalZoneTemp;

  Detection({
    required this.bbox,
    required this.label,
    required this.confidence,
    this.thermalZoneTemp,
  });

  @override
  String toString() =>
      'Detection(label: $label, conf: ${confidence.toStringAsFixed(2)})';
}

// ─── Isolate payload ──────────────────────────────────────────────────────────

class _PreprocessRequest {
  final Uint8List jpegBytes;
  final int inputSize;
  const _PreprocessRequest({
    required this.jpegBytes,
    required this.inputSize,
  });
}

// ─── Service ──────────────────────────────────────────────────────────────────

/// Runs YOLOv8n TFLite inference using a Dart Isolate for preprocessing.
/// Model: assets/best.tflite
/// Output shape: [1, 12, 8400] — 4 bbox + 8 class scores × 8400 anchors
class TFLiteService {
  Interpreter? _interpreter;
  bool _loading = false;

  static const List<String> _labels = [
    'lying', 'standing', 'walking', 'sitting',
    'feeding', 'drinking', 'social_interaction', 'aggression',
  ];

  // Lowered from 0.35 → 0.25 to account for real-world lighting variance
  static const double _confThreshold = 0.25;
  static const double _iouThreshold  = 0.45;
  static const int    _inputSize     = 640;

  bool get isLoaded => _interpreter != null;

  // ── Load ──────────────────────────────────────────────────────────────────

  Future<void> loadModel() async {
    if (_interpreter != null || _loading) return;
    _loading = true;
    try {
      final options = InterpreterOptions()..threads = 2;
      _interpreter = await Interpreter.fromAsset(
        'assets/best.tflite',
        options: options,
      );
      final shape = _interpreter!.getInputTensor(0).shape;
      debugPrint('[TFLite] Model loaded. Input shape: $shape');
    } catch (e) {
      debugPrint('[TFLite] Load error: $e');
    } finally {
      _loading = false;
    }
  }

  // ── Inference ─────────────────────────────────────────────────────────────

  /// Runs inference. Image preprocessing is offloaded to a background isolate.
  /// The isolate returns a proper 4D List [1][H][W][3] that tflite_flutter
  /// can correctly walk — no .reshape() call needed (which doesn't exist on
  /// typed lists and was the root cause of zero-detection output).
  Future<List<Detection>> runInference(Uint8List jpegBytes) async {
    if (_interpreter == null) return [];

    // 1. Offload decode + resize + normalize to background isolate
    final input4d = await compute(_preprocessImage, _PreprocessRequest(
      jpegBytes: jpegBytes,
      inputSize: _inputSize,
    ));

    if (input4d == null) return [];

    // 2. Output buffer [1, 12, 8400]
    final output = List.generate(1, (_) =>
      List.generate(12, (_) => List<double>.filled(8400, 0.0)));

    // 3. Run inference — input4d is already [1][640][640][3], no reshape needed
    try {
      _interpreter!.run(input4d, output);
    } catch (e) {
      debugPrint('[TFLite] run error: $e');
      return [];
    }

    // 4. Parse YOLOv8 output: tensor[row][anchor]
    final List<Detection> dets = [];
    final tensor = output[0]; // [12][8400]

    for (int i = 0; i < 8400; i++) {
      double maxScore = 0.0;
      int classId = -1;

      for (int c = 4; c < 12; c++) {
        final score = tensor[c][i];
        if (score > maxScore) {
          maxScore = score;
          classId = c - 4;
        }
      }

      if (maxScore >= _confThreshold && classId >= 0) {
        // YOLOv8 bbox: center_x, center_y, width, height (pixel coords in input space)
        final cx = tensor[0][i];
        final cy = tensor[1][i];
        final w  = tensor[2][i];
        final h  = tensor[3][i];

        // Normalize to [0, 1] for display scaling
        final left   = (cx - w / 2) / _inputSize;
        final top    = (cy - h / 2) / _inputSize;
        final width  = w / _inputSize;
        final height = h / _inputSize;

        if (width > 0 && height > 0) {
          dets.add(Detection(
            bbox: Rect.fromLTWH(left, top, width, height),
            label: _labels[classId],
            confidence: maxScore,
          ));
        }
      }
    }

    debugPrint('[TFLite] Raw detections before NMS: ${dets.length}');
    return _nms(dets);
  }

  // ── Worker (runs inside Isolate) ──────────────────────────────────────────

  /// Returns a proper 4D List<List<List<List<double>>>> of shape [1][H][W][3].
  /// tflite_flutter's native bridge walks this structure correctly.
  /// DO NOT return Float32List here — .reshape() does not exist on typed lists
  /// and would produce garbage input to the model.
  static List<List<List<List<double>>>>? _preprocessImage(_PreprocessRequest req) {
    final image = img.decodeJpg(req.jpegBytes);
    if (image == null) return null;

    final resized = img.copyResize(
      image,
      width: req.inputSize,
      height: req.inputSize,
      interpolation: img.Interpolation.linear,
    );

    // Build [1][3][H][W] — aligning with NCHW export layout
    final rChannel = List.generate(req.inputSize, (_) => List.filled(req.inputSize, 0.0));
    final gChannel = List.generate(req.inputSize, (_) => List.filled(req.inputSize, 0.0));
    final bChannel = List.generate(req.inputSize, (_) => List.filled(req.inputSize, 0.0));

    for (int y = 0; y < req.inputSize; y++) {
      for (int x = 0; x < req.inputSize; x++) {
        final pixel = resized.getPixel(x, y);
        rChannel[y][x] = pixel.r / 255.0;
        gChannel[y][x] = pixel.g / 255.0;
        bChannel[y][x] = pixel.b / 255.0;
      }
    }

    return [[rChannel, gChannel, bChannel]];
  }

  // ── NMS helpers ───────────────────────────────────────────────────────────

  static List<Detection> _nms(List<Detection> dets) {
    dets.sort((a, b) => b.confidence.compareTo(a.confidence));
    final kept = <Detection>[];
    for (final det in dets) {
      if (kept.every((k) => _iou(k.bbox, det.bbox) < _iouThreshold)) {
        kept.add(det);
      }
    }
    return kept;
  }

  static double _iou(Rect a, Rect b) {
    final ix = a.intersect(b);
    if (ix.isEmpty) return 0;
    final intersection = ix.width * ix.height;
    final union = a.width * a.height + b.width * b.height - intersection;
    return union > 0 ? intersection / union : 0;
  }

  void dispose() => _interpreter?.close();
}
