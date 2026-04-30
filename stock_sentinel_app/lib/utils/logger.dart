import 'package:flutter/foundation.dart';

/// 统一日志工具 — release模式下静默，debug模式输出
class AppLog {
  static void d(String tag, String message) {
    if (kDebugMode) {
      debugPrint('[$tag] $message');
    }
  }

  static void e(String tag, String message, [Object? error]) {
    if (kDebugMode) {
      debugPrint('[$tag] ERROR: $message${error != null ? ' - $error' : ''}');
    }
  }

  static void w(String tag, String message) {
    if (kDebugMode) {
      debugPrint('[$tag] WARN: $message');
    }
  }
}
