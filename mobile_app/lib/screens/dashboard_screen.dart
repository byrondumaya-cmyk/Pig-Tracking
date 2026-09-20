import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'package:gal/gal.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';
import '../services/tflite_service.dart';
import '../widgets/live_feed_widget.dart';
import '../widgets/thermal_grid_widget.dart';
import '../widgets/status_chip.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'settings_screen.dart';

class AmbientData {
  final double? tempC;
  final double? humidityPct;
  final double? thi;
  final bool isHeatStress;
  const AmbientData({this.tempC, this.humidityPct, this.thi, this.isHeatStress = false});
}

class PenAlert {
  final int id;
  final String alertType;
  final bool resolved;
  const PenAlert({required this.id, required this.alertType, required this.resolved});
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final TFLiteService _tflite = TFLiteService();
  List<Detection> _currentDetections = [];
  bool _isProcessingFrame = false;
  int _frameCount = 0;
  double _fps = 0.0;
  DateTime _fpsTimer = DateTime.now();
  AmbientData? _ambient;
  List<PenAlert> _alerts = [];
  bool _hasUnresolved = false;
  Timer? _pollTimer;
  final Set<int> _seenAlertIds = {}; // tracks known alert IDs to detect new ones

  @override
  void initState() {
    super.initState();
    _loadThresholds();
    _tflite.loadModel();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<WebsocketService>().addListener(_onWsData);
    });
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) => _pollPiData());
    _pollPiData();
  }

  Future<void> _loadThresholds() async {
    final prefs = await SharedPreferences.getInstance();
    final conf = prefs.getDouble('confidence_threshold') ?? 0.25;
    final iou = prefs.getDouble('iou_threshold') ?? 0.45;
    _tflite.updateThresholds(confidence: conf, iou: iou);
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    try { context.read<WebsocketService>().removeListener(_onWsData); } catch (_) {}
    _tflite.dispose();
    super.dispose();
  }

  void _onWsData() {
    final data = context.read<WebsocketService>().latestData;
    if (data == null) return;
    _frameCount++;
    final now = DateTime.now();
    final elapsed = now.difference(_fpsTimer).inMilliseconds;
    if (elapsed >= 1000) {
      final newFps = _frameCount * 1000.0 / elapsed;
      _frameCount = 0;
      _fpsTimer = now;
      if (mounted) setState(() => _fps = newFps);
    }
    _runInference(data.imageBytes);
  }

  Future<void> _runInference(imageBytes) async {
    if (_isProcessingFrame || !_tflite.isLoaded) return;
    _isProcessingFrame = true;
    try {
      final detections = await _tflite.runInference(imageBytes);
      if (mounted) setState(() => _currentDetections = detections);
    } catch (e) {
      debugPrint('[Dashboard] Inference error: $e');
    } finally {
      _isProcessingFrame = false;
    }
  }

  Future<void> _pollPiData() async {
    final ip = context.read<WebsocketService>().savedIp ?? '192.168.4.1';
    final base = 'http://$ip:5000';
    try {
      final r = await http.get(Uri.parse('$base/api/ambient')).timeout(const Duration(seconds: 4));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body) as Map<String, dynamic>;
        if (mounted) setState(() => _ambient = AmbientData(
          tempC: (j['temp_c'] as num?)?.toDouble(),
          humidityPct: (j['humidity_pct'] as num?)?.toDouble(),
          thi: (j['thi'] as num?)?.toDouble(),
          isHeatStress: j['is_heat_stress'] == true,
        ));
      }
    } catch (_) {}
    try {
      final r = await http.get(Uri.parse('$base/api/pen_alerts')).timeout(const Duration(seconds: 4));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body) as Map<String, dynamic>;
        final list = (j['alerts'] as List).map((a) => PenAlert(
          id: a['id'] as int,
          alertType: (a['alert_type'] ?? 'unknown') as String,
          resolved: a['resolved'] == true,
        )).toList();

        // Detect new unresolved alerts and snapshot the current frame
        for (final alert in list) {
          if (!alert.resolved && !_seenAlertIds.contains(alert.id)) {
            _captureAlertScreenshot(alert.alertType);
          }
        }
        // Track all seen IDs so we don't double-snapshot
        _seenAlertIds.addAll(list.map((a) => a.id));

        if (mounted) setState(() { _alerts = list; _hasUnresolved = j['has_unresolved'] == true; });
      }
    } catch (_) {}
  }

  Future<void> _captureAlertScreenshot(String alertType) async {
    final ws = context.read<WebsocketService>();
    final imageBytes = ws.latestData?.imageBytes;
    if (imageBytes == null || imageBytes.isEmpty) return;
    try {
      await Gal.putImageBytes(
        imageBytes,
        album: 'Pig Alerts',
      );
      debugPrint('[Screenshot] Saved alert snapshot');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('📸 Alert snapshot saved: ${alertType.replaceAll("_", " ")}'),
          backgroundColor: Colors.orange.shade800,
          duration: const Duration(seconds: 4),
        ));
      }
    } catch (e) {
      debugPrint('[Screenshot] Failed to save: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final ws = context.watch<WebsocketService>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          if (_hasUnresolved)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Badge(
                label: const Text('!'),
                child: Icon(Icons.warning_amber_rounded, color: Colors.orange.shade300),
              ),
            ),
          Center(child: StatusChip(state: ws.state)),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () async {
              await Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen()));
              _loadThresholds();
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
    if (ws.latestData == null) return const Center(child: CircularProgressIndicator());
    final data = ws.latestData!;
    return Column(children: [
      Expanded(flex: 5, child: Stack(fit: StackFit.expand, children: [
        LiveFeedWidget(imageBytes: data.imageBytes, detections: _currentDetections),
        Positioned(top: 8, right: 8, child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: Colors.black.withOpacity(0.6), borderRadius: BorderRadius.circular(6)),
          child: Text('${_fps.toStringAsFixed(1)} FPS',
            style: const TextStyle(color: Colors.greenAccent, fontSize: 11, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
        )),
      ])),
      Expanded(flex: 5, child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(flex: 3, child: Column(children: [
            Card(child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
              child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
                _ambientChip(Icons.thermostat, '${_ambient?.tempC?.toStringAsFixed(1) ?? '--'}°C', 'Temp'),
                _ambientChip(Icons.water_drop, '${_ambient?.humidityPct?.toStringAsFixed(0) ?? '--'}%', 'Humidity'),
                _ambientChip(Icons.wb_sunny, 'THI ${_ambient?.thi?.toStringAsFixed(1) ?? '--'}', 'Heat Index',
                  color: _ambient?.isHeatStress == true ? Colors.orange : null),
              ]),
            )),
            const SizedBox(height: AppSpacing.sm),
            Expanded(child: Card(child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Live Detections', style: AppText.h3),
                const SizedBox(height: AppSpacing.sm),
                if (_currentDetections.isEmpty)
                  const Expanded(child: Center(child: Text('No subjects detected', style: AppText.body)))
                else
                  Expanded(child: ListView.builder(
                    itemCount: _currentDetections.length,
                    itemBuilder: (_, i) {
                      final det = _currentDetections[i];
                      final meta = kBehaviorMap[det.label];
                      return ListTile(dense: true, contentPadding: EdgeInsets.zero,
                        leading: Icon(meta?.icon ?? Icons.help_outline, color: meta?.color, size: 20),
                        title: Text(meta?.label ?? det.label, style: AppText.body),
                        trailing: Text('${(det.confidence * 100).toInt()}%', style: AppText.mono));
                    },
                  )),
              ]),
            ))),
          ])),
          const SizedBox(width: AppSpacing.sm),
          Expanded(flex: 2, child: Column(children: [
            Expanded(flex: 3, child: Card(child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Thermal Grid', style: AppText.h3),
                const SizedBox(height: AppSpacing.sm),
                Expanded(child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: ThermalGridWidget(grid: data.thermalGrid),
                )),
              ]),
            ))),
            const SizedBox(height: AppSpacing.sm),
            Expanded(flex: 2, child: Card(
              color: _hasUnresolved ? Colors.orange.shade900.withOpacity(0.25) : null,
              child: Padding(padding: const EdgeInsets.all(AppSpacing.sm), child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Icon(Icons.warning_amber_rounded, size: 13,
                      color: _hasUnresolved ? Colors.orange : AppColors.textMuted),
                    const SizedBox(width: 4),
                    Text('Pi Alerts', style: AppText.h3.copyWith(fontSize: 12)),
                  ]),
                  const SizedBox(height: 4),
                  if (_alerts.isEmpty)
                    const Expanded(child: Center(child: Text('No alerts', style: AppText.body)))
                  else
                    Expanded(child: ListView.builder(
                      itemCount: _alerts.length.clamp(0, 5),
                      itemBuilder: (_, i) {
                        final a = _alerts[i];
                        return Padding(padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(children: [
                            Icon(a.resolved ? Icons.check_circle_outline : Icons.error_outline,
                              size: 12, color: a.resolved ? Colors.green : Colors.orange),
                            const SizedBox(width: 4),
                            Expanded(child: Text(a.alertType.replaceAll('_', ' '),
                              style: TextStyle(fontSize: 10,
                                color: a.resolved ? AppColors.textMuted : Colors.orange.shade200),
                              overflow: TextOverflow.ellipsis)),
                          ]));
                      },
                    )),
                ],
              )),
            )),
          ])),
        ]),
      )),
    ]);
  }

  Widget _ambientChip(IconData icon, String value, String label, {Color? color}) {
    return Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 16, color: color ?? AppColors.textMuted),
      Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: color)),
      Text(label, style: AppText.body.copyWith(fontSize: 9, color: AppColors.textMuted)),
    ]);
  }

  Widget _buildOfflineState(WebsocketService ws) {
    return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(Icons.wifi_off, size: 48, color: AppColors.textMuted.withOpacity(0.5)),
      const SizedBox(height: AppSpacing.md),
      const Text('Connection Lost', style: AppText.h2),
      const SizedBox(height: AppSpacing.sm),
      Text(ws.errorMessage ?? 'Ensure the Pi is powered on and reachable.',
        style: AppText.body, textAlign: TextAlign.center),
      const SizedBox(height: AppSpacing.lg),
      ElevatedButton.icon(
        onPressed: ws.savedIp != null ? () => ws.connect(ws.savedIp!) : null,
        icon: const Icon(Icons.refresh),
        label: const Text('Retry Connection'),
      ),
    ]));
  }
}
