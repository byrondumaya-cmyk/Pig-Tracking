import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/constants.dart';
import '../core/theme.dart';

/// Initial screen shown when no saved Pi IP exists.
/// User enters the Pi IP, taps Connect → saved to SharedPreferences.
class ConnectScreen extends StatefulWidget {
  final void Function(String ip) onConnected;
  const ConnectScreen({super.key, required this.onConnected});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _controller = TextEditingController(text: '192.168.4.1');
  final _formKey = GlobalKey<FormState>();
  bool _connecting = false;

  static const _prefKey = 'pi_ip_address';

  @override
  void initState() {
    super.initState();
    _loadSavedIp();
  }

  Future<void> _loadSavedIp() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_prefKey);
    if (saved != null && mounted) {
      setState(() => _controller.text = saved);
    }
  }

  Future<void> _connect() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final ip = _controller.text.trim();

    setState(() => _connecting = true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefKey, ip);

    if (mounted) widget.onConnected(ip);
    setState(() => _connecting = false);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: AppSpacing.xxl),

              // ── Logo / Icon ─────────────────────────────────────────────
              Container(
                width: 64, height: 64,
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.primary.withOpacity(0.3)),
                ),
                child: const Icon(
                  Icons.sensors, color: AppColors.primary, size: 32,
                ),
              ),
              const SizedBox(height: AppSpacing.lg),

              // ── Title ────────────────────────────────────────────────────
              const Text('Swine Health\nMonitor', style: AppText.h1),
              const SizedBox(height: AppSpacing.xs),
              const Text(
                'Connect to your Raspberry Pi sensor hub',
                style: AppText.body,
              ),
              const SizedBox(height: AppSpacing.xxl),

              // ── Form ─────────────────────────────────────────────────────
              Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text('Pi IP Address', style: AppText.h3),
                    const SizedBox(height: AppSpacing.sm),
                    TextFormField(
                      controller: _controller,
                      keyboardType: TextInputType.url,
                      style: AppText.mono.copyWith(
                        color: AppColors.textPrimary, fontSize: 15,
                      ),
                      decoration: const InputDecoration(
                        hintText: '192.168.4.1',
                        prefixIcon: Icon(
                          Icons.wifi, color: AppColors.textMuted, size: 18,
                        ),
                      ),
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) {
                          return 'Enter the Pi IP address';
                        }
                        // Basic IP format check
                        final parts = v.trim().split('.');
                        if (parts.length != 4) return 'Enter a valid IP (e.g. 192.168.4.1)';
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'AP Mode: 192.168.4.1  •  LAN: Check your router',
                      style: AppText.label,
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    // ── Connect Button ─────────────────────────────────────
                    SizedBox(
                      height: 50,
                      child: ElevatedButton.icon(
                        onPressed: _connecting ? null : _connect,
                        icon: _connecting
                            ? const SizedBox(
                                width: 18, height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.play_arrow_rounded, size: 20),
                        label: Text(_connecting ? 'Connecting…' : 'Connect'),
                      ),
                    ),
                  ],
                ),
              ),

              const Spacer(),

              // ── Footer ───────────────────────────────────────────────────
              Center(
                child: Text(
                  'YOLOv8n · mAP50 0.827 · 8 behaviors',
                  style: AppText.label,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
