import 'package:flutter/material.dart';

// ─── Color Palette ───────────────────────────────────────────────────────────
class AppColors {
  AppColors._();

  static const background   = Color(0xFF0D1117);
  static const surface      = Color(0xFF161B22);
  static const surfaceAlt   = Color(0xFF21262D);
  static const border       = Color(0xFF30363D);

  static const primary      = Color(0xFF2EA043);   // Healthy green
  static const primaryLight = Color(0xFF3FB950);
  static const warning      = Color(0xFFE3B341);   // Caution amber
  static const danger       = Color(0xFFF85149);   // Alert red
  static const info         = Color(0xFF58A6FF);   // Info blue

  static const textPrimary   = Color(0xFFF0F6FC);
  static const textSecondary = Color(0xFF8B949E);
  static const textMuted     = Color(0xFF6E7681);

  // Thermal gradient — cold → hot
  static const thermalCold   = Color(0xFF0D47A1);
  static const thermalMid    = Color(0xFF4CAF50);
  static const thermalWarm   = Color(0xFFFF9800);
  static const thermalHot    = Color(0xFFF44336);
}

// ─── Text Styles ─────────────────────────────────────────────────────────────
class AppText {
  AppText._();

  static const h1 = TextStyle(
    fontSize: 24, fontWeight: FontWeight.w700,
    color: AppColors.textPrimary, letterSpacing: -0.5,
  );
  static const h2 = TextStyle(
    fontSize: 18, fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );
  static const h3 = TextStyle(
    fontSize: 14, fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );
  static const body = TextStyle(
    fontSize: 13, fontWeight: FontWeight.w400,
    color: AppColors.textSecondary, height: 1.5,
  );
  static const label = TextStyle(
    fontSize: 11, fontWeight: FontWeight.w500,
    color: AppColors.textMuted, letterSpacing: 0.5,
  );
  static const mono = TextStyle(
    fontSize: 12, fontFamily: 'monospace',
    color: AppColors.textSecondary,
  );
}

// ─── Spacing ─────────────────────────────────────────────────────────────────
class AppSpacing {
  AppSpacing._();
  static const xs  = 4.0;
  static const sm  = 8.0;
  static const md  = 16.0;
  static const lg  = 24.0;
  static const xl  = 32.0;
  static const xxl = 48.0;
}

// ─── Behavior Classes ────────────────────────────────────────────────────────
class BehaviorMeta {
  const BehaviorMeta({required this.label, required this.color, required this.icon});
  final String label;
  final Color color;
  final IconData icon;
}

const Map<String, BehaviorMeta> kBehaviorMap = {
  'lying':              BehaviorMeta(label: 'Lying',             color: Color(0xFF58A6FF), icon: Icons.airline_seat_flat),
  'standing':           BehaviorMeta(label: 'Standing',          color: Color(0xFF3FB950), icon: Icons.accessibility_new),
  'walking':            BehaviorMeta(label: 'Walking',           color: Color(0xFF79C0FF), icon: Icons.directions_walk),
  'sitting':            BehaviorMeta(label: 'Sitting',           color: Color(0xFFA5D6FF), icon: Icons.chair),
  'feeding':            BehaviorMeta(label: 'Feeding',           color: Color(0xFFE3B341), icon: Icons.restaurant),
  'drinking':           BehaviorMeta(label: 'Drinking',          color: Color(0xFF56D364), icon: Icons.water_drop),
  'social_interaction': BehaviorMeta(label: 'Social',            color: Color(0xFFD2A8FF), icon: Icons.groups),
  'aggression':         BehaviorMeta(label: 'Aggression',        color: Color(0xFFF85149), icon: Icons.warning_amber),
};
