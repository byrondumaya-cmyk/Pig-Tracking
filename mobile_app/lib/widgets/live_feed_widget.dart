import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../services/tflite_service.dart';
import '../core/constants.dart';

class LiveFeedWidget extends StatelessWidget {
  final Uint8List imageBytes;
  final List<Detection> detections;

  const LiveFeedWidget({
    super.key,
    required this.imageBytes,
    required this.detections,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        // Camera Feed
        Image.memory(
          imageBytes,
          fit: BoxFit.cover,
          gaplessPlayback: true,
        ),
        
        // Bounding Boxes
        if (detections.isNotEmpty)
          CustomPaint(
            painter: _DetectionOverlayPainter(detections: detections),
          ),
      ],
    );
  }
}

class _DetectionOverlayPainter extends CustomPainter {
  final List<Detection> detections;

  _DetectionOverlayPainter({required this.detections});

  @override
  void paint(Canvas canvas, Size size) {
    // Note: This assumes YOLOv8 output coordinates are normalized (0-1).
    // If they are absolute (0-640), they need to be scaled by size.width/640.
    // For this implementation, we assume the TFLiteService scales them to 0-1 or we scale here.
    // Assuming they are unscaled (0-640) for now, as that's typical from raw tensors before UI projection.
    final scaleX = size.width / 640.0;
    final scaleY = size.height / 640.0;

    for (final det in detections) {
      final color = kBehaviorMap[det.label]?.color ?? Colors.greenAccent;
      
      final paint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0;

      // Scale bbox to canvas size
      final rect = Rect.fromLTRB(
        det.bbox.left * scaleX,
        det.bbox.top * scaleY,
        det.bbox.right * scaleX,
        det.bbox.bottom * scaleY,
      );

      canvas.drawRect(rect, paint);

      // Label background
      final bgPaint = Paint()
        ..color = color
        ..style = PaintingStyle.fill;
        
      final textSpan = TextSpan(
        text: '${det.label} ${(det.confidence * 100).toInt()}%',
        style: const TextStyle(
          color: Colors.black,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      );
      
      final textPainter = TextPainter(
        text: textSpan,
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      
      final labelBgRect = Rect.fromLTWH(
        rect.left,
        rect.top - textPainter.height - 2,
        textPainter.width + 4,
        textPainter.height + 2,
      );
      
      canvas.drawRect(labelBgRect, bgPaint);
      textPainter.paint(canvas, Offset(rect.left + 2, rect.top - textPainter.height - 1));
    }
  }

  @override
  bool shouldRepaint(covariant _DetectionOverlayPainter oldDelegate) {
    return true; // Always repaint when detections change
  }
}
