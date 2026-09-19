import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/websocket_service.dart';
import '../services/tflite_service.dart';

class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final TFLiteService _tflite = TFLiteService();

  @override
  void initState() {
    super.initState();
    _tflite.loadModel();
    // Auto-connect to Pi's AP Gateway IP
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<WebsocketService>(context, listen: false).connect('192.168.4.1');
    });
  }

  @override
  Widget build(BuildContext context) {
    final ws = Provider.of<WebsocketService>(context);

    return Scaffold(
      backgroundColor: Color(0xFF1E1E1E),
      appBar: AppBar(
        title: Text('Swine Health Monitor (Hybrid)'),
        backgroundColor: Colors.black87,
        actions: [
          Icon(
            ws.isConnected ? Icons.wifi : Icons.wifi_off,
            color: ws.isConnected ? Colors.green : Colors.red,
          ),
          SizedBox(width: 16)
        ],
      ),
      body: Column(
        children: [
          _buildLiveFeed(ws),
          _buildTelemetry(ws),
        ],
      ),
    );
  }

  Widget _buildLiveFeed(WebsocketService ws) {
    if (ws.latestData == null) {
      return Expanded(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text(
                "Connecting to Sensor Hub...",
                style: TextStyle(color: Colors.white70),
              )
            ],
          ),
        ),
      );
    }

    // Run inference on the latest frame
    // Note: In production this should be isolate-backed to prevent UI stutter
    final detections = _tflite.runInference(ws.latestData!.imageBytes);

    return Expanded(
      flex: 2,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.memory(
            ws.latestData!.imageBytes,
            fit: BoxFit.cover,
            gaplessPlayback: true,
          ),
          // Bounding Box Overlay
          ...detections.map((det) => Positioned(
            left: det.bbox.left,
            top: det.bbox.top,
            width: det.bbox.width,
            height: det.bbox.height,
            child: Container(
              decoration: BoxDecoration(
                border: Border.all(color: Colors.greenAccent, width: 2),
              ),
              child: Align(
                alignment: Alignment.topLeft,
                child: Container(
                  color: Colors.greenAccent,
                  padding: EdgeInsets.all(2),
                  child: Text(
                    "${det.label} ${(det.confidence*100).toStringAsFixed(1)}%",
                    style: TextStyle(color: Colors.black, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ),
          ))
        ],
      ),
    );
  }

  Widget _buildTelemetry(WebsocketService ws) {
    return Expanded(
      flex: 1,
      child: Container(
        padding: EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.black87,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Edge Inference", style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
            SizedBox(height: 10),
            Text(
              "TFLite Model: YOLOv8s INT8", 
              style: TextStyle(color: Colors.white70)
            ),
            SizedBox(height: 10),
            if (ws.latestData != null)
              Text(
                "Thermal Grid: ${ws.latestData!.thermalGrid.length > 0 ? 'Active' : 'Offline'}",
                style: TextStyle(color: ws.latestData!.thermalGrid.length > 0 ? Colors.green : Colors.red),
              )
          ],
        ),
      ),
    );
  }
}
