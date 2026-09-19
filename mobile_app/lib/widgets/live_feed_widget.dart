import 'dart:typed_data';
import 'package:flutter/material.dart';

class LiveFeedWidget extends StatelessWidget {
  final Uint8List imageBytes;

  const LiveFeedWidget({
    super.key,
    required this.imageBytes,
  });

  @override
  Widget build(BuildContext context) {
    return Image.memory(
      imageBytes,
      fit: BoxFit.cover,
      gaplessPlayback: true,
    );
  }
}
