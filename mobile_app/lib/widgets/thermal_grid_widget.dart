import 'dart:ui' show ImageFilter;
import 'package:flutter/material.dart';
import '../core/constants.dart';

class ThermalGridWidget extends StatelessWidget {
  final List<List<double>> grid; // 32x24 grid from MLX90640
  final double minTemp;
  final double maxTemp;

  const ThermalGridWidget({
    super.key,
    required this.grid,
    this.minTemp = 20.0,
    this.maxTemp = 40.0,
  });

  @override
  Widget build(BuildContext context) {
    if (grid.isEmpty || grid[0].isEmpty) {
      return Container(
        color: Colors.black26,
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.thermostat, color: AppColors.textMuted, size: 32),
              SizedBox(height: 8),
              Text('Thermal Offline', style: AppText.label),
            ],
          ),
        ),
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        return ImageFiltered(
          imageFilter: ImageFilter.blur(sigmaX: 4.0, sigmaY: 4.0),
          child: CustomPaint(
            size: Size(constraints.maxWidth, constraints.maxHeight),
            painter: _ThermalPainter(grid: grid, minTemp: minTemp, maxTemp: maxTemp),
          ),
        );
      },
    );
  }
}

class _ThermalPainter extends CustomPainter {
  final List<List<double>> grid;
  final double minTemp;
  final double maxTemp;

  _ThermalPainter({required this.grid, required this.minTemp, required this.maxTemp});

  @override
  void paint(Canvas canvas, Size size) {
    final int rows = grid.length;
    final int cols = grid[0].length;
    final double cellWidth = size.width / cols;
    final double cellHeight = size.height / rows;

    final paint = Paint()..style = PaintingStyle.fill;

    for (int y = 0; y < rows; y++) {
      for (int x = 0; x < cols; x++) {
        final temp = grid[y][x];
        paint.color = _getColorForTemp(temp);
        
        final rect = Rect.fromLTWH(x * cellWidth, y * cellHeight, cellWidth, cellHeight);
        canvas.drawRect(rect, paint);
      }
    }
  }

  Color _getColorForTemp(double temp) {
    // Normalize temp to 0.0 - 1.0 range
    double t = (temp - minTemp) / (maxTemp - minTemp);
    t = t.clamp(0.0, 1.0);

    // Multi-stop gradient mapping
    if (t < 0.33) {
      return Color.lerp(AppColors.thermalCold, AppColors.thermalMid, t / 0.33)!;
    } else if (t < 0.66) {
      return Color.lerp(AppColors.thermalMid, AppColors.thermalWarm, (t - 0.33) / 0.33)!;
    } else {
      return Color.lerp(AppColors.thermalWarm, AppColors.thermalHot, (t - 0.66) / 0.34)!;
    }
  }

  @override
  bool shouldRepaint(covariant _ThermalPainter oldDelegate) {
    // For performance, we'd normally do a deep compare or pass a hash, 
    // but since we redraw on every frame, always returning true is acceptable for now.
    return true; 
  }
}
