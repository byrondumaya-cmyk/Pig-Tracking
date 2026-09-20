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

class _PreprocessRequest {
  final Uint8List jpegBytes;
  final int inputSize;
  final bool isQuantized;
  const _PreprocessRequest({
    required this.jpegBytes,
    required this.inputSize,
    required this.isQuantized,
  });
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

  // ── Inference ─────────────────────────────────────────────────────────────

  /// Runs inference. Image preprocessing is offloaded to a background isolate 
  /// to keep the UI smooth and prevent OOM crashes.
  Future<List<Detection>> runInference(Uint8List jpegBytes) async {
    if (_interpreter == null) return [];

    final inputTensor = _interpreter!.getInputTensor(0);
    final isQuantized = inputTensor.type == TfLiteType.uint8 || inputTensor.type == TfLiteType.int8;

    // 1. Offload heavy image decoding, resizing, and buffer flattening to a background isolate
    final flatInput = await compute(_preprocessImage, _PreprocessRequest(
      jpegBytes: jpegBytes,
      inputSize: _inputSize,
      isQuantized: isQuantized,
    ));

    if (flatInput == null) return [];

    // 2. Prepare output tensor [1, 12, 8400]
    // YOLOv8 output is typically float32 even if quantized, but we use nested lists 
    // because tflite_flutter's run() handles the mapping to the output array gracefully.
    final output = List.generate(1, (_) =>
      List.generate(12, (_) => List<double>.filled(8400, 0.0)));

    // 3. Run inference on the main isolate (very fast, ~20ms, since prep is done)
    // We pass the flat buffer; tflite_flutter will reshape it to [1, 640, 640, 3] internally.
    try {
      // For input, tflite_flutter accepts flat lists and reshapes them automatically
      // if the total element count matches.
      final reshapedInput = flatInput.reshape([1, _inputSize, _inputSize, 3]);
      _interpreter!.run(reshapedInput, output);
    } catch (e) {
      debugPrint('[TFLite] run error: $e');
      return [];
    }
    
    // 4. Parse YOLOv8 output
    final List<Detection> dets = [];
    final tensor = output[0]; // [12, 8400] -> 4 bbox coords + 8 class scores
    
    for (int i = 0; i < 8400; i++) {
      double maxClassScore = 0.0;
      int classId = -1;
      
      for (int c = 4; c < 12; c++) {
        final score = tensor[c][i];
        if (score > maxClassScore) {
          maxClassScore = score;
          classId = c - 4;
        }
      }
      
      if (maxClassScore >= _confThreshold) {
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

  // ── Worker (runs inside Isolate) ──────────────────────────────────────────

  static dynamic _preprocessImage(_PreprocessRequest req) {
    final image = img.decodeJpg(req.jpegBytes);
    if (image == null) return null;

    final resized = img.copyResize(image, width: req.inputSize, height: req.inputSize);
    final numPixels = req.inputSize * req.inputSize;

    if (req.isQuantized) {
      final buffer = Uint8List(numPixels * 3);
      int offset = 0;
      for (int y = 0; y < req.inputSize; y++) {
        for (int x = 0; x < req.inputSize; x++) {
          final pixel = resized.getPixel(x, y);
          buffer[offset++] = pixel.r.toInt();
          buffer[offset++] = pixel.g.toInt();
          buffer[offset++] = pixel.b.toInt();
        }
      }
      return buffer;
    } else {
      final buffer = Float32List(numPixels * 3);
      int offset = 0;
      for (int y = 0; y < req.inputSize; y++) {
        for (int x = 0; x < req.inputSize; x++) {
          final pixel = resized.getPixel(x, y);
          buffer[offset++] = pixel.r / 255.0;
          buffer[offset++] = pixel.g / 255.0;
          buffer[offset++] = pixel.b / 255.0;
        }
      }
      return buffer;
    }
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
