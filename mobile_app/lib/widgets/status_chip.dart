import 'package:flutter/material.dart';
import '../services/websocket_service.dart';
import '../core/constants.dart';

class StatusChip extends StatelessWidget {
  final WsConnectionState state;

  const StatusChip({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final Color color;
    final String text;
    final IconData icon;

    switch (state) {
      case WsConnectionState.connected:
        color = AppColors.primary;
        text = 'Online';
        icon = Icons.wifi;
      case WsConnectionState.connecting:
        color = AppColors.warning;
        text = 'Connecting';
        icon = Icons.wifi_find;
      case WsConnectionState.error:
        color = AppColors.danger;
        text = 'Error';
        icon = Icons.error_outline;
      case WsConnectionState.disconnected:
        color = AppColors.textMuted;
        text = 'Offline';
        icon = Icons.wifi_off;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            text,
            style: AppText.label.copyWith(color: color, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
