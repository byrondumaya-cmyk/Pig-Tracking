import 'dart:async';
import 'dart:isolate';
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

class _InferenceRequest {
  final Uint8List jpegBytes;
  final int interpreterAddress;
  const _InferenceRequest(this.jpegBytes, this.interpreterAddress);
}

// ─── Service ──────────────────────────────────────────────────────────────────

/// Runs YOLOv8n TFLite inference off the UI thread using a Dart Isolate.
/// Model: assets/best.tflite (INT8 quantized, 640×640 input)
/// Output shape: [1, 12, 8400] — 4 bbox + 8 class scores × 8400 anchors
class TFLiteService {
  Interpreter? _interpreter;
  bool _loading = false;

  static const List<String> _labels = [
    'lying', 'standing', 'walking', 'sitting',
    'feeding', 'drinking', 'social_interaction', 'aggression',
  ];

  static const double _confThreshold = 0.35;
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
      debugPrint('[TFLite] Model loaded. Input: ${_interpreter!.getInputTensor(0).shape}');
    } catch (e) {
      debugPrint('[TFLite] Load error: $e');
    } finally {
      _loading = false;
    }
  }

  // ── Inference (Isolate-backed) ────────────────────────────────────────────

  /// Runs inference off the UI thread via [compute].
  /// Returns parsed [Detection] list after NMS.
  Future<List<Detection>> runInferenceAsync(Uint8List jpegBytes) async {
    if (_interpreter == null) return [];
    return compute(_inferenceWorker, _InferenceRequest(jpegBytes, _interpreter!.address));
  }

  /// Sync fallback for direct calls (no UI-thread isolation).
  List<Detection> runInference(Uint8List jpegBytes) {
    if (_interpreter == null) return [];
    return _inferenceWorker(_InferenceRequest(jpegBytes, _interpreter!.address));
  }

  // ── Worker (runs inside Isolate) ──────────────────────────────────────────

  static List<Detection> _inferenceWorker(_InferenceRequest request) {
    // 1. Decode + resize
    final image = img.decodeJpg(request.jpegBytes);
    if (image == null) return [];

    final resized = img.copyResize(image, width: _inputSize, height: _inputSize);

    // 2. Normalize to [0, 1] Float32
    final input = List.generate(
      1,
      (_) => List.generate(
        _inputSize,
        (y) => List.generate(
          _inputSize,
          (x) {
            final pixel = resized.getPixel(x, y);
            return [
              pixel.r / 255.0,
              pixel.g / 255.0,
              pixel.b / 255.0,
            ];
          },
        ),
      ),
    );

    // 3. Run — output shape [1, 12, 8400]
    final output = List.generate(1, (_) =>
      List.generate(12, (_) => List<double>.filled(8400, 0.0)));

    // Reconstruct interpreter from address
    final interpreter = Interpreter.fromAddress(request.interpreterAddress);
    interpreter.run(input, output);
    
    // Parse YOLOv8 output
    final List<Detection> dets = [];
    final tensor = output[0]; // [12, 8400] -> 4 bbox coords + 8 class scores
    
    for (int i = 0; i < 8400; i++) {
      double maxClassScore = 0.0;
      int classId = -1;
      
      // Classes are at indices 4 to 11
      for (int c = 4; c < 12; c++) {
        final score = tensor[c][i];
        if (score > maxClassScore) {
          maxClassScore = score;
          classId = c - 4;
        }
      }
      
      if (maxClassScore >= _confThreshold) {
        // YOLOv8 bbox format: center_x, center_y, width, height (normalized to input size)
        final cx = tensor[0][i];
        final cy = tensor[1][i];
        final w = tensor[2][i];
        final h = tensor[3][i];
        
        final left = (cx - w / 2) / _inputSize;
        final top = (cy - h / 2) / _inputSize;
        final width = w / _inputSize;
        final height = h / _inputSize;
        
        dets.add(Detection(
          bbox: Rect.fromLTWH(left, top, width, height),
          label: _labels[classId],
          confidence: maxClassScore,
        ));
      }
    }

    return _nms(dets);
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
