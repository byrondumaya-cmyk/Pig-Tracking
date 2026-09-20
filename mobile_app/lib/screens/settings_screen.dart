import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import '../core/constants.dart';
import '../services/websocket_service.dart';

// ─── Constants ────────────────────────────────────────────────────────────────

const String _kIpKey = 'saved_ip';
const String _kConfKey = 'confidence_threshold';
const String _kIouKey = 'iou_threshold';

// ─── Screen ───────────────────────────────────────────────────────────────────

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // -- Local state
  final _ipCtrl = TextEditingController();
  double _confidence = 0.25;
  double _iou = 0.45;
  bool _saving = false;

  // -- Pi-side state
  bool _loadingConfig = true;
  bool _loadingRecipients = true;
  List<Map<String, dynamic>> _recipients = [];
  Map<String, dynamic> _alertConfig = {};
  final _phoneCtrl = TextEditingController();

  String get _baseUrl {
    final ip = _ipCtrl.text.trim().isNotEmpty ? _ipCtrl.text.trim() : '192.168.4.1';
    return 'http://admin:PigDashboard2026!@$ip:5000';
  }

  @override
  void initState() {
    super.initState();
    _loadLocal();
  }

  @override
  void dispose() {
    _ipCtrl.dispose();
    _phoneCtrl.dispose();
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
    _loadPiData();
  }

  Future<void> _saveLocal() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kIpKey, _ipCtrl.text.trim());
    await prefs.setDouble(_kConfKey, _confidence);
    await prefs.setDouble(_kIouKey, _iou);
  }

  // ── Pi API helpers ───────────────────────────────────────────────────────

  Future<void> _loadPiData() async {
    await Future.wait([_loadRecipients(), _loadAlertConfig()]);
  }

  Future<void> _loadRecipients() async {
    setState(() => _loadingRecipients = true);
    try {
      final r = await http
          .get(Uri.parse('$_baseUrl/api/recipients'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body) as Map<String, dynamic>;
        if (mounted) setState(() => _recipients = List<Map<String, dynamic>>.from(j['recipients'] ?? []));
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingRecipients = false);
  }

  Future<void> _loadAlertConfig() async {
    setState(() => _loadingConfig = true);
    try {
      final r = await http
          .get(Uri.parse('$_baseUrl/api/alert_config'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body) as Map<String, dynamic>;
        if (mounted) setState(() => _alertConfig = Map<String, dynamic>.from(j['config'] ?? {}));
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingConfig = false);
  }

  Future<void> _addRecipient() async {
    final phone = _phoneCtrl.text.trim();
    if (phone.isEmpty) return;
    try {
      final r = await http
          .post(
            Uri.parse('$_baseUrl/api/recipients'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'phone_number': phone}),
          )
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 201) {
        _phoneCtrl.clear();
        _loadRecipients();
        if (mounted) _showSnack('✅ Recipient added');
      } else {
        if (mounted) _showSnack('❌ Failed: ${jsonDecode(r.body)['message']}');
      }
    } catch (e) {
      if (mounted) _showSnack('❌ Cannot reach Pi');
    }
  }

  Future<void> _deleteRecipient(int id) async {
    try {
      final r = await http
          .delete(Uri.parse('$_baseUrl/api/recipients/$id'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        _loadRecipients();
        if (mounted) _showSnack('🗑 Recipient removed');
      }
    } catch (_) {
      if (mounted) _showSnack('❌ Cannot reach Pi');
    }
  }

  Future<void> _resetToDefaults() async {
    try {
      final r = await http
          .get(Uri.parse('$_baseUrl/api/alert_config/defaults'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body) as Map<String, dynamic>;
        final defaults = j['defaults'] ?? j['config'] ?? j;
        if (mounted) {
          setState(() {
            _alertConfig = Map<String, dynamic>.from(defaults);
            _confidence = 0.25;
            _iou = 0.45;
          });
          _showSnack('✅ Defaults loaded — tap Save to apply');
        }
      }
    } catch (_) {
      // Fallback to hardcoded defaults if Pi unreachable
      if (mounted) {
        setState(() {
          _alertConfig = {
            'stationary_alert_minutes': 30.0,
            'fever_delta_threshold_c': 1.5,
            'population_lethargy_ratio': 0.6,
            'thi_heat_stress_threshold': 79.0,
            'cooldown_minutes': 30,
          };
          _confidence = 0.25;
          _iou = 0.45;
        });
        _showSnack('✅ Defaults loaded (offline fallback)');
      }
    }
  }

  Future<void> _saveAll() async {
    setState(() => _saving = true);
    await _saveLocal();
    try {
      final body = <String, dynamic>{};
      if (_alertConfig.isNotEmpty) {
        for (final key in ['stationary_alert_minutes', 'fever_delta_threshold_c',
            'population_lethargy_ratio', 'thi_heat_stress_threshold', 'cooldown_minutes']) {
          if (_alertConfig.containsKey(key)) body[key] = _alertConfig[key];
        }
      }
      if (body.isNotEmpty) {
        await http
            .patch(
              Uri.parse('$_baseUrl/api/alert_config'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(body),
            )
            .timeout(const Duration(seconds: 5));
      }
      if (mounted) _showSnack('✅ Settings saved');
    } catch (_) {
      if (mounted) _showSnack('⚠ Local settings saved. Pi unreachable.');
    }
    if (mounted) setState(() => _saving = false);
  }

  void _showSnack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: const Duration(seconds: 3)),
    );
  }

  // ── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
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
            onPressed: _saving ? null : _saveAll,
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
          const SizedBox(height: AppSpacing.md),

          _sectionHeader(Icons.notifications_active, 'Alert Thresholds (Pi)'),
          _loadingConfig
              ? const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()))
              : _alertConfig.isEmpty
                  ? _offlineBanner()
                  : _card([
                      _numericTile(
                        label: 'Stationary Alert (min)',
                        key_: 'stationary_alert_minutes',
                        hint: '30',
                        tooltip: 'Minutes a pig must remain stationary before triggering a lethargy alert.',
                      ),
                      const Divider(height: 1),
                      _numericTile(
                        label: 'Fever Delta Threshold (°C)',
                        key_: 'fever_delta_threshold_c',
                        hint: '1.5',
                        isDecimal: true,
                        tooltip: 'Thermal delta above ambient to flag as a fever symptom.',
                      ),
                      const Divider(height: 1),
                      _numericTile(
                        label: 'Herd Lethargy Ratio',
                        key_: 'population_lethargy_ratio',
                        hint: '0.6',
                        isDecimal: true,
                        tooltip: 'Fraction of herd that must be lethargic to trigger a population alert.',
                      ),
                      const Divider(height: 1),
                      _numericTile(
                        label: 'Heat Stress THI',
                        key_: 'thi_heat_stress_threshold',
                        hint: '79.0',
                        isDecimal: true,
                        tooltip: 'Temperature Humidity Index above which heat stress is flagged.',
                      ),
                      const Divider(height: 1),
                      _numericTile(
                        label: 'SMS Cooldown (min)',
                        key_: 'cooldown_minutes',
                        hint: '30',
                        tooltip: 'Minimum minutes between repeated SMS alerts for the same alert type.',
                      ),
                    ]),
          const SizedBox(height: AppSpacing.md),

          _sectionHeader(Icons.contact_phone, 'SMS Alert Recipients (Pi)'),
          _card([
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(children: [
                Expanded(
                  child: TextField(
                    controller: _phoneCtrl,
                    decoration: _inputDecor('+639XXXXXXXXX'),
                    keyboardType: TextInputType.phone,
                    inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[+\d]'))],
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                FilledButton(
                  onPressed: _addRecipient,
                  child: const Text('Add'),
                ),
              ]),
            ),
            const Divider(height: 1),
            if (_loadingRecipients)
              const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator()))
            else if (_recipients.isEmpty)
              const Padding(
                padding: EdgeInsets.all(AppSpacing.md),
                child: Text('No recipients configured.', style: AppText.body),
              )
            else
              ..._recipients.map((r) => ListTile(
                leading: Icon(
                  r['enabled'] == true ? Icons.phone_enabled : Icons.phone_disabled,
                  color: r['enabled'] == true ? AppColors.primary : AppColors.textMuted,
                  size: 20,
                ),
                title: Text(r['phone_number'] ?? '', style: AppText.body),
                subtitle: Text(r['enabled'] == true ? 'Active' : 'Disabled', style: AppText.label),
                trailing: IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18, color: AppColors.danger),
                  onPressed: () => _deleteRecipient(r['id'] as int),
                ),
              )),
          ]),
          const SizedBox(height: AppSpacing.xl),
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

  Widget _numericTile({
    required String label,
    required String key_,
    required String hint,
    bool isDecimal = false,
    String? tooltip,
  }) {
    final rawVal = _alertConfig[key_];
    final strVal = rawVal != null ? rawVal.toString() : '';
    return ListTile(
      title: Text(label, style: AppText.body),
      subtitle: tooltip != null ? Text(tooltip, style: AppText.label) : null,
      trailing: SizedBox(
        width: 90,
        child: TextField(
          controller: TextEditingController(text: strVal),
          decoration: _inputDecor(hint).copyWith(
            contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          ),
          keyboardType: TextInputType.numberWithOptions(decimal: isDecimal),
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(isDecimal ? r'[\d.]' : r'\d')),
          ],
          textAlign: TextAlign.center,
          onChanged: (v) {
            final parsed = isDecimal ? double.tryParse(v) : int.tryParse(v);
            if (parsed != null) {
              setState(() => _alertConfig[key_] = parsed);
            }
          },
        ),
      ),
    );
  }

  Widget _offlineBanner() => Padding(
    padding: const EdgeInsets.all(AppSpacing.md),
    child: Row(children: [
      const Icon(Icons.signal_wifi_off, color: AppColors.warning, size: 16),
      const SizedBox(width: 8),
      Expanded(
        child: Text(
          'Pi unreachable — connect to pig-farm Wi-Fi first.',
          style: AppText.body.copyWith(color: AppColors.warning),
        ),
      ),
      TextButton(onPressed: _loadPiData, child: const Text('Retry')),
    ]),
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
