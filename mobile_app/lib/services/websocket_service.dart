import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

// ─── Models ──────────────────────────────────────────────────────────────────

class SensorData {
  final Uint8List imageBytes;
  final List<List<double>> thermalGrid;
  final List<Map<String, dynamic>> detections;
  final DateTime receivedAt;

  const SensorData({
    required this.imageBytes,
    required this.thermalGrid,
    required this.detections,
    required this.receivedAt,
  });
}

// ─── Connection State ─────────────────────────────────────────────────────────

enum WsConnectionState { disconnected, connecting, connected, error }

// ─── Service ──────────────────────────────────────────────────────────────────

class WebsocketService extends ChangeNotifier {
  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;

  SensorData? _latestData;
  WsConnectionState _state = WsConnectionState.disconnected;
  String? _errorMessage;
  String? _savedIp;

  // ── Getters ───────────────────────────────────────────────────────────────
  SensorData? get latestData => _latestData;
  WsConnectionState get state => _state;
  bool get isConnected => _state == WsConnectionState.connected;
  String? get errorMessage => _errorMessage;
  String? get savedIp => _savedIp;

  // Exponential backoff delays (seconds)
  static const _backoffDelays = [3, 5, 10, 30];
  int _reconnectAttempt = 0;

  // ── Public API ────────────────────────────────────────────────────────────

  /// Connect to the Pi's WebSocket server at ws://[ip]:8765
  void connect(String ipAddress) {
    if (_state == WsConnectionState.connecting ||
        _state == WsConnectionState.connected) return;

    _savedIp = ipAddress;
    _reconnectAttempt = 0;
    _doConnect(ipAddress);
  }

  void disconnect() {
    _cancelReconnect();
    _closeChannel();
    _setState(WsConnectionState.disconnected);
    _errorMessage = null;
    notifyListeners();
  }

  // ── Internal ──────────────────────────────────────────────────────────────

  void _doConnect(String ip) {
    _setState(WsConnectionState.connecting);

    try {
      final uri = Uri.parse('ws://$ip:8765');
      _channel = WebSocketChannel.connect(uri);

      _sub = _channel!.stream.listen(
        _onMessage,
        onDone: () => _onDisconnected('Connection closed'),
        onError: (e) => _onDisconnected('Stream error: $e'),
        cancelOnError: true,
      );

      _setState(WsConnectionState.connected);
      _reconnectAttempt = 0;
      _errorMessage = null;
      notifyListeners();
    } catch (e) {
      _onDisconnected('Failed to connect: $e');
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final decoded = jsonDecode(raw as String) as Map<String, dynamic>;
      if (decoded['type'] != 'sync_frame') return;

      final imageBytes = base64Decode(decoded['image'] as String);
      final rawGrid = decoded['thermal_grid'] as List?;
      final thermalGrid = rawGrid != null
          ? rawGrid
              .map((row) => (row as List)
                  .map((v) => (v as num).toDouble())
                  .toList())
              .toList()
          : <List<double>>[];
          
      final rawDets = decoded['detections'] as List?;
      final detections = rawDets != null 
          ? rawDets.cast<Map<String, dynamic>>()
          : <Map<String, dynamic>>[];

      _latestData = SensorData(
        imageBytes: imageBytes,
        thermalGrid: thermalGrid,
        detections: detections,
        receivedAt: DateTime.now(),
      );
      notifyListeners();
    } catch (e) {
      debugPrint('[WS] Failed to parse frame: $e');
    }
  }

  void _onDisconnected(String reason) {
    _closeChannel();
    _errorMessage = reason;
    _setState(WsConnectionState.error);
    notifyListeners();
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_savedIp == null) return;
    _cancelReconnect();

    final delayIndex = _reconnectAttempt.clamp(0, _backoffDelays.length - 1);
    final delay = Duration(seconds: _backoffDelays[delayIndex]);
    _reconnectAttempt++;

    debugPrint('[WS] Reconnecting in ${delay.inSeconds}s (attempt $_reconnectAttempt)…');

    _reconnectTimer = Timer(delay, () {
      if (_savedIp != null) _doConnect(_savedIp!);
    });
  }

  void _cancelReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
  }

  void _closeChannel() {
    _sub?.cancel();
    _sub = null;
    _channel?.sink.close();
    _channel = null;
  }

  void _setState(WsConnectionState s) {
    _state = s;
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
