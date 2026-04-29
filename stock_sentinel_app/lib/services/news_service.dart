import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

/// 新闻服务 — 本地缓存 + 后台自动刷新
class NewsService {
  static final NewsService _instance = NewsService._internal();
  factory NewsService() => _instance;
  NewsService._internal();

  final _api = ApiService();
  List<Map<String, dynamic>> _news = [];
  bool _loaded = false;
  DateTime? _lastFetch;
  Timer? _autoRefresh;

  static const _cacheKey = 'news_raw_cache';
  static const _cacheTsKey = 'news_raw_cache_ts';
  static const _refreshInterval = Duration(minutes: 3);

  List<Map<String, dynamic>> get news => _news;
  bool get isLoaded => _loaded;

  /// 初始化：先加载本地缓存，再后台刷新
  Future<void> init() async {
    await _loadLocalCache();
    // 启动自动刷新
    _startAutoRefresh();
    // 后台拉最新
    refresh();
  }

  /// 加载本地缓存
  Future<void> _loadLocalCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cached = prefs.getString(_cacheKey);
      if (cached != null && cached.isNotEmpty) {
        final List<dynamic> decoded = jsonDecode(cached);
        _news = decoded.cast<Map<String, dynamic>>();
        _loaded = true;
        debugPrint('📰 本地缓存加载: ${_news.length}条');
      }
    } catch (e) {
      debugPrint('📰 本地缓存加载失败: $e');
    }
  }

  /// 保存到本地缓存
  Future<void> _saveLocalCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cacheKey, jsonEncode(_news));
      await prefs.setInt(_cacheTsKey, DateTime.now().millisecondsSinceEpoch);
    } catch (e) {
      debugPrint('📰 本地缓存保存失败: $e');
    }
  }

  /// 刷新新闻
  Future<void> refresh() async {
    try {
      final data = await _api.getNewsRaw(limit: 200);
      if (data.isNotEmpty) {
        _news = data;
        _loaded = true;
        _lastFetch = DateTime.now();
        await _saveLocalCache();
        debugPrint('📰 新闻刷新: ${_news.length}条');
        _onUpdate?.call();
      }
    } catch (e) {
      debugPrint('📰 新闻刷新失败: $e');
    }
  }

  VoidCallback? _onUpdate;

  void addListener(VoidCallback cb) => _onUpdate = cb;
  void removeListener(VoidCallback cb) => _onUpdate = null;

  void _startAutoRefresh() {
    _autoRefresh?.cancel();
    _autoRefresh = Timer.periodic(_refreshInterval, (_) => refresh());
  }

  void dispose() {
    _autoRefresh?.cancel();
  }

  /// 清空缓存
  Future<void> clearCache() async {
    _news = [];
    _loaded = false;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_cacheKey);
    await prefs.remove(_cacheTsKey);
  }
}
