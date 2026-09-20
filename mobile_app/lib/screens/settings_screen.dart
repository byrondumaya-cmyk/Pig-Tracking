import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/constants.dart';
import '../services/websocket_service.dart';

// ─── Constants ────────────────────────────────────────────────────────────────

const String _kIpKey = 'pi_ip_address';
const String _kConfKey = 'confidence_threshold';
const String _kIouKey = 'iou_threshold';

// ─── Screen ───────────────────────────────────────────────────────────────────

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _ipCtrl = TextEditingController();
  double _confidence = 0.25;
  double _iou = 0.45;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadLocal();
  }

  @override
  void dispose() {
    _ipCtrl.dispose();
    super.dispose();
  }

  // ── Local prefs ─────────────────────────────────────────────────────────

  Future<void> _loadLocal() async {
    final prefs = await SharedPreferences.getInstance();
    final ws = context.read<WebsocketService>();
    setState(() {
      _ipCtrl.text = prefs.getString(_kIpKey) ?? ws.savedIp ?? '192.168.4.1';
      _confidence = prefs.getDouble(_kConfKey) ?? 0.25;
      _iou = prefs.getDouble(_kIouKey) ?? 0.45;
    });
  }

  Future<void> _saveLocal() async {
    setState(() => _saving = true);
    final prefs = await SharedPreferences.getInstance();
    final newIp = _ipCtrl.text.trim();
    
    await prefs.setString(_kIpKey, newIp);
    await prefs.setDouble(_kConfKey, _confidence);
    await prefs.setDouble(_kIouKey, _iou);

    if (mounted) {
      final ws = context.read<WebsocketService>();
      // Reconnect immediately to the new IP
      if (ws.savedIp != newIp || !ws.isConnected) {
        ws.disconnect();
        ws.connect(newIp);
      }
      _showSnack('✅ Settings saved');
      setState(() => _saving = false);
    }
  }

  Future<void> _resetToDefaults() async {
    setState(() {
      _ipCtrl.text = '192.168.4.1';
      _confidence = 0.25;
      _iou = 0.45;
    });
    _showSnack('✅ Defaults loaded — tap Save to apply');
  }

  void _showSnack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: const Duration(seconds: 3)),
    );
  }

  // ── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final ws = context.watch<WebsocketService>();
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Device Settings'),
        actions: [
          TextButton.icon(
            onPressed: _resetToDefaults,
            icon: const Icon(Icons.restore, size: 18),
            label: const Text('Defaults'),
          ),
          const SizedBox(width: 4),
          FilledButton.icon(
            onPressed: _saving ? null : _saveLocal,
            icon: _saving
                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.save, size: 18),
            label: const Text('Save'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          // Connection Status Banner
          if (ws.state == WsConnectionState.error || ws.state == WsConnectionState.disconnected)
            _offlineBanner(ws.errorMessage ?? 'Disconnected'),

          _sectionHeader(Icons.wifi, 'Connection'),
          _card([
            _labeledField(
              label: 'Pi IP Address',
              child: TextField(
                controller: _ipCtrl,
                decoration: _inputDecor('e.g. 192.168.4.1'),
                keyboardType: TextInputType.url,
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
                onChanged: (_) => setState(() {}),
              ),
            ),
          ]),
          const SizedBox(height: AppSpacing.md),

          _sectionHeader(Icons.manage_search, 'Detection Tuning (Local)'),
          _card([
            _sliderTile(
              label: 'Confidence Threshold',
              value: _confidence,
              min: 0.1, max: 0.9,
              divisions: 16,
              tooltip: 'Minimum score to consider a detection valid. Lower = more detections, less accurate.',
              onChanged: (v) => setState(() => _confidence = double.parse(v.toStringAsFixed(2))),
            ),
            const Divider(height: 1),
            _sliderTile(
              label: 'IOU Threshold (NMS)',
              value: _iou,
              min: 0.1, max: 0.9,
              divisions: 16,
              tooltip: 'Overlap tolerance for bounding box suppression. Higher = fewer merged boxes.',
              onChanged: (v) => setState(() => _iou = double.parse(v.toStringAsFixed(2))),
            ),
          ]),
        ],
      ),
    );
  }

  // ── Helpers ─────────────────────────────────────────────────────────────

  Widget _sectionHeader(IconData icon, String title) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
    child: Row(children: [
      Icon(icon, size: 16, color: AppColors.info),
      const SizedBox(width: 6),
      Text(title, style: AppText.h3.copyWith(color: AppColors.info)),
    ]),
  );

  Widget _card(List<Widget> children) => Card(
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: children),
  );

  Widget _labeledField({required String label, required Widget child}) => Padding(
    padding: const EdgeInsets.all(AppSpacing.md),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: AppText.label),
      const SizedBox(height: 4),
      child,
    ]),
  );

  Widget _sliderTile({
    required String label,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String tooltip,
    required ValueChanged<double> onChanged,
  }) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(label, style: AppText.body)),
        Text(value.toStringAsFixed(2), style: AppText.mono.copyWith(color: AppColors.primary)),
      ]),
      Slider(value: value, min: min, max: max, divisions: divisions, onChanged: onChanged),
      Text(tooltip, style: AppText.label),
    ]),
  );

  Widget _offlineBanner(String error) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.md),
    child: Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.danger.withOpacity(0.1),
        border: Border.all(color: AppColors.danger.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(children: [
        const Icon(Icons.signal_wifi_off, color: AppColors.danger, size: 20),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Connection Lost', style: AppText.body.copyWith(color: AppColors.danger, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(error, style: AppText.label.copyWith(color: AppColors.danger)),
            ],
          ),
        ),
      ]),
    ),
  );

  InputDecoration _inputDecor(String hint) => InputDecoration(
    hintText: hint,
    hintStyle: AppText.label,
    filled: true,
    fillColor: AppColors.surfaceAlt,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8),
      borderSide: const BorderSide(color: AppColors.border),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8),
      borderSide: const BorderSide(color: AppColors.border),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(8),
      borderSide: const BorderSide(color: AppColors.info),
    ),
  );
}
