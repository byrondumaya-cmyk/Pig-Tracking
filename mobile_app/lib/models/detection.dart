import 'dart:ui';

/// Represents a single detected pig bounding box from the Pi's AI inference.
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
