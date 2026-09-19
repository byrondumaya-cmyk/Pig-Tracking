import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/theme.dart';
import 'services/websocket_service.dart';
import 'screens/connect_screen.dart';
import 'screens/dashboard_screen.dart';

void main() {
  // Ensure bindings are initialized before calling runApp
  WidgetsFlutterBinding.ensureInitialized();
  
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => WebsocketService()),
      ],
      child: const SwineHealthApp(),
    ),
  );
}

class SwineHealthApp extends StatefulWidget {
  const SwineHealthApp({super.key});

  @override
  State<SwineHealthApp> createState() => _SwineHealthAppState();
}

class _SwineHealthAppState extends State<SwineHealthApp> {
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Swine Health Monitor',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      navigatorKey: _navigatorKey,
      
      // Default route handles the IP connection first
      home: ConnectScreen(
        onConnected: (ip) {
          // Tell the WS service to connect
          context.read<WebsocketService>().connect(ip);
          // Navigate to dashboard
          _navigatorKey.currentState?.pushReplacement(
            MaterialPageRoute(builder: (_) => const DashboardScreen()),
          );
        },
      ),
    );
  }
}
