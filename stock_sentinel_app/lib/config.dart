import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  // 腾讯云服务器
  static const String apiBase = 'http://124.221.94.233/api';
  static const String wsUrl = 'ws://124.221.94.233/api/ws';
  // Android模拟器
  // static const String apiBase = 'http://10.0.2.2:8000/api';
  // static const String wsUrl = 'ws://10.0.2.2:8000/api/ws';

  // ── 用户认证状态 ──
  static String? _token;
  static Map<String, dynamic>? _user;

  static String? get token => _token;
  static Map<String, dynamic>? get user => _user;
  static bool get isLoggedIn => _token != null && _token!.isNotEmpty;
  static String get nickname => _user?['nickname'] ?? '游客';
  // 功能开关（未想好商业模式前全部隐藏）
  static const bool enablePremium = false;

  static bool _isPremium = false;
  static bool get isPremium => _isPremium;
  static set isPremium(bool v) => _isPremium = v;

  static Future<void> loadPremium() async {
    final prefs = await SharedPreferences.getInstance();
    _isPremium = prefs.getBool('is_premium') ?? false;
  }

  static Future<void> savePremium(bool v) async {
    _isPremium = v;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('is_premium', v);
  }

  /// 从本地存储加载token
  static Future<void> loadAuth() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
    final userStr = prefs.getString('auth_user');
    if (userStr != null && userStr.isNotEmpty) {
      try {
        final decoded = jsonDecode(userStr);
        if (decoded is Map) _user = Map<String, dynamic>.from(decoded);
      } catch (_) {
        _user = null;
      }
    }
    await loadPremium();
  }

  static Future<void> saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
  }

  static Future<void> saveUser(Map<String, dynamic> user) async {
    _user = user;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_user', jsonEncode(user));
  }

  static Future<void> logout() async {
    _token = null;
    _user = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('auth_user');
  }
}
