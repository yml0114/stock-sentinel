import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config.dart';
import 'providers/watchlist_provider.dart';
import 'providers/events_provider.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppConfig.loadAuth();
  runApp(const StockSentinelApp());
}

class StockSentinelApp extends StatelessWidget {
  const StockSentinelApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => WatchlistProvider()),
        ChangeNotifierProvider(create: (_) => EventsProvider()),
      ],
      child: MaterialApp(
        title: '金融哨兵',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          colorSchemeSeed: const Color(0xFF4A90D9),
          scaffoldBackgroundColor: const Color(0xFF0D0D1A),
          cardTheme: CardThemeData(
            color: const Color(0xFF16213E),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF0D0D1A),
            elevation: 0,
            centerTitle: true,
            titleTextStyle: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          floatingActionButtonTheme: const FloatingActionButtonThemeData(
            backgroundColor: Color(0xFF4A90D9),
            foregroundColor: Colors.white,
          ),
          snackBarTheme: SnackBarThemeData(
            backgroundColor: const Color(0xFF16213E),
            contentTextStyle: const TextStyle(color: Colors.white),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          dialogTheme: DialogThemeData(
            backgroundColor: const Color(0xFF16213E),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
        home: const _AuthGate(),
      ),
    );
  }
}

/// 认证门控 — 未登录显示登录页，已登录直接进主页
class _AuthGate extends StatefulWidget {
  const _AuthGate();
  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  bool _skipped = false;

  @override
  Widget build(BuildContext context) {
    if (AppConfig.isLoggedIn || _skipped) {
      return const HomeScreen();
    }
    return LoginScreen(
      onLoginSuccess: () {
        setState(() {}); // 切换到 HomeScreen
      },
      onSkip: () {
        setState(() => _skipped = true); // 跳过，以游客身份进入
      },
    );
  }
}
