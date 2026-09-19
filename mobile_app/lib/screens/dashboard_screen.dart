import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';
import '../services/tflite_service.dart';
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
  final TFLiteService _tflite = TFLiteService();
  List<Detection> _currentDetections = [];
  bool _isProcessingFrame = false;

  @override
  void initState() {
    super.initState();
    _tflite.loadModel();
  }

  @override
  void dispose() {
    _tflite.dispose();
    super.dispose();
  }

  Future<void> _processFrame(SensorData data) async {
    if (_isProcessingFrame || !_tflite.isLoaded) return;

    _isProcessingFrame = true;
    try {
      // Run async isolate inference
      final detections = await _tflite.runInferenceAsync(data.imageBytes);
      if (mounted) {
        setState(() => _currentDetections = detections);
      }
    } catch (e) {
      debugPrint('[Dashboard] Inference error: $e');
    } finally {
      _isProcessingFrame = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final ws = context.watch<WebsocketService>();

    // Kick off inference if we have new data and aren't already processing
    if (ws.latestData != null) {
      _processFrame(ws.latestData!);
    }

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
        // Top Half: Live Feed (Local Inference)
        Expanded(
          flex: 5,
          child: LiveFeedWidget(
            imageBytes: data.imageBytes,
            detections: _currentDetections,
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
                          const Text('Live Detections', style: AppText.h3),
                          const SizedBox(height: AppSpacing.sm),
                          if (_currentDetections.isEmpty)
                            const Expanded(child: Center(child: Text('No subjects detected', style: AppText.body)))
                          else
                            Expanded(
                              child: ListView.builder(
                                itemCount: _currentDetections.length,
                                itemBuilder: (context, i) {
                                  final det = _currentDetections[i];
                                  final meta = kBehaviorMap[det.label];
                                  return ListTile(
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                    leading: Icon(meta?.icon ?? Icons.help_outline, color: meta?.color, size: 20),
                                    title: Text(meta?.label ?? det.label, style: AppText.body),
                                    trailing: Text('${(det.confidence * 100).toInt()}%', style: AppText.mono),
                                  );
                                },
                              ),
                            ),
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
