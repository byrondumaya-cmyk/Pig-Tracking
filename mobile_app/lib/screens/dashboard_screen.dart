import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';
import '../widgets/live_feed_widget.dart';
import '../widgets/thermal_grid_widget.dart';
import '../widgets/status_chip.dart';
import 'settings_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  Widget build(BuildContext context) {
    final ws = context.watch<WebsocketService>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          Center(child: StatusChip(state: ws.state)),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SettingsScreen()),
              );
            },
          ),
          const SizedBox(width: AppSpacing.sm),
        ],
      ),
      body: ws.state == WsConnectionState.disconnected || ws.state == WsConnectionState.error
          ? _buildOfflineState(ws)
          : _buildDashboard(ws),
    );
  }

  Widget _buildDashboard(WebsocketService ws) {
    if (ws.latestData == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final data = ws.latestData!;

    return Column(
      children: [
        // Top Half: Live Feed (Annotated by Server)
        Expanded(
          flex: 5,
          child: LiveFeedWidget(
            imageBytes: data.imageBytes,
          ),
        ),
        
        // Bottom Half: Telemetry & Thermal
        Expanded(
          flex: 4,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Left Column: Behaviors & Stats
                Expanded(
                  flex: 3,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Live Annotations', style: AppText.h3),
                          const SizedBox(height: AppSpacing.sm),
                          const Expanded(
                            child: Center(
                              child: Text('Detections are now handled and drawn by the Raspberry Pi for 100% accuracy sync.', 
                                style: AppText.body, 
                                textAlign: TextAlign.center,
                              ),
                            ),
                          )
                        ],
                      ),
                    ),
                  ),
                ),
                
                const SizedBox(width: AppSpacing.md),
                
                // Right Column: Thermal
                Expanded(
                  flex: 2,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Thermal Grid', style: AppText.h3),
                          const SizedBox(height: AppSpacing.sm),
                          Expanded(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: ThermalGridWidget(grid: data.thermalGrid),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildOfflineState(WebsocketService ws) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.wifi_off, size: 48, color: AppColors.textMuted.withOpacity(0.5)),
          const SizedBox(height: AppSpacing.md),
          const Text('Connection Lost', style: AppText.h2),
          const SizedBox(height: AppSpacing.sm),
          Text(
            ws.errorMessage ?? 'Ensure the Pi is powered on and reachable.',
            style: AppText.body,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.lg),
          ElevatedButton.icon(
            onPressed: ws.savedIp != null ? () => ws.connect(ws.savedIp!) : null,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry Connection'),
          ),
        ],
      ),
    );
  }
}
