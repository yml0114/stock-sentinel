import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/watchlist_provider.dart';
import 'providers/events_provider.dart';
import 'screens/home_screen.dart';

void main() {
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
        home: const HomeScreen(),
      ),
    );
  }
}
