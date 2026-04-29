import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../services/translator_service.dart';

/// 新闻服务 — 本地缓存 + 后台自动刷新 + 本地翻译
class NewsService {
  static final NewsService _instance = NewsService._internal();
  factory NewsService() => _instance;
  NewsService._internal();

  final _api = ApiService();
  final _translator = TranslatorService();
  List<Map<String, dynamic>> _news = [];
  bool _loaded = false;
  DateTime? _lastFetch;
  Timer? _autoRefresh;
  int _translatedCount = 0;
  int _totalCount = 0;

  static const _cacheKey = 'news_raw_cache';
  static const _cacheTsKey = 'news_raw_cache_ts';
  static const _refreshInterval = Duration(minutes: 3);

  List<Map<String, dynamic>> get news => _news;
  bool get isLoaded => _loaded;
  int get translatedCount => _translatedCount;
  int get totalCount => _totalCount;
  bool get isTranslating => _translatedCount < _totalCount && _totalCount > 0;

  /// 初始化：先加载本地缓存，再后台刷新
  Future<void> init() async {
    await _loadLocalCache();
    _startAutoRefresh();
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
        _totalCount = _news.length;
        // 统计已翻译数量
        _translatedCount = _news.where((n) => 
          (n['title_cn'] ?? '').toString().isNotEmpty || 
          !_translator.isEnglish((n['title'] ?? '').toString())
        ).length;
        debugPrint('📰 本地缓存加载: ${_news.length}条, 已翻译: $_translatedCount');
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
        _totalCount = _news.length;
        _translatedCount = 0;
        await _saveLocalCache();
        debugPrint('📰 新闻刷新: ${_news.length}条');
        _onUpdate?.call();
        
        // 后台逐条翻译英文新闻
        _translateNewsBackground();
      }
    } catch (e) {
      debugPrint('📰 新闻刷新失败: $e');
    }
  }

  /// 后台翻译新闻列表（边翻译边更新UI）
  Future<void> _translateNewsBackground() async {
    for (int i = 0; i < _news.length; i++) {
      final item = _news[i];
      final title = (item['title'] ?? '').toString();
      final content = (item['content'] ?? '').toString();
      
      // 如果标题已经是中文，跳过
      if (!_translator.isEnglish(title)) {
        _translatedCount++;
        continue;
      }
      
      try {
        // 翻译标题
        final titleCn = await _translator.translate(title);
        if (titleCn != title) {
          item['title_cn'] = titleCn;
        }
        
        // 翻译内容摘要（如果有）
        if (content.isNotEmpty && _translator.isEnglish(content)) {
          final contentCn = await _translator.translate(
            content.length > 200 ? content.substring(0, 200) : content
          );
          if (contentCn != content) {
            item['content_cn'] = contentCn;
          }
        }
        
        _translatedCount++;
        _onUpdate?.call(); // 通知UI刷新
        
        // 小延迟，避免API限流
        await Future.delayed(const Duration(milliseconds: 100));
      } catch (e) {
        _translatedCount++;
        debugPrint('📰 翻译失败 [${title.substring(0, title.length > 20 ? 20 : title.length)}]: $e');
      }
    }
    
    // 全部翻译完成，保存缓存
    await _saveLocalCache();
    debugPrint('📰 翻译完成: $_translatedCount/$_totalCount');
    _onUpdate?.call();
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
    _translatedCount = 0;
    _totalCount = 0;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_cacheKey);
    await prefs.remove(_cacheTsKey);
  }
}
