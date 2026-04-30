import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import '../utils/logger.dart';

/// APP端本地翻译服务 — 4引擎并行竞争，取最快结果
class TranslatorService {
  static final TranslatorService _instance = TranslatorService._internal();
  factory TranslatorService() => _instance;
  TranslatorService._internal();

  final Dio _dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 8),
  ));

  /// 翻译缓存（英文原文 → 中文译文）
  final Map<String, String> _cache = {};

  /// 检测文本是否主要是英文
  bool isEnglish(String text) {
    if (text.isEmpty) return false;
    int asciiCount = 0;
    int total = 0;
    for (int i = 0; i < text.length && i < 100; i++) {
      final c = text.codeUnitAt(i);
      if (c > 0x7F) continue; // 跳过非ASCII
      total++;
      if ((c >= 0x41 && c <= 0x5A) || (c >= 0x61 && c <= 0x7A)) {
        asciiCount++;
      }
    }
    if (total < 5) return false;
    return asciiCount / total > 0.6;
  }

  /// 翻译文本（4引擎并行竞争）
  Future<String> translate(String text) async {
    if (text.isEmpty || !isEnglish(text)) return text;
    
    // 检查缓存
    if (_cache.containsKey(text)) return _cache[text]!;
    
    // 4引擎并行竞争
    final futures = <Future<String?>>[
      _translateSimplyTranslate(text),
      _translateJina(text),
      _translateYoudao(text),
      _translateMyMemory(text),
    ];
    
    // 取最快的成功结果
    try {
      final result = await Future.any(futures.where((f) => f != null).cast<Future<String?>>());
      if (result != null && result.isNotEmpty) {
        _cache[text] = result;
        AppLog.d('Translate', '翻译完成: ${text.substring(0, text.length > 30 ? 30 : text.length)}...');
        return result;
      }
    } catch (e) {
      AppLog.e('Translate', '翻译失败', e);
    }
    
    return text; // 翻译失败返回原文
  }

  /// 引擎1: SimplyTranslate（Google翻译代理）
  Future<String?> _translateSimplyTranslate(String text) async {
    try {
      final res = await _dio.get(
        'https://simplytranslate.org/api/translate',
        queryParameters: {
          'engine': 'google',
          'from': 'en',
          'to': 'zh',
          'text': text,
        },
      );
      if (res.statusCode == 200) {
        final data = res.data;
        if (data is Map && data['translated-text'] != null) {
          return data['translated-text'].toString();
        }
      }
    } catch (_) {}
    return null;
  }

  /// 引擎2: Jina AI（免费翻译API）
  Future<String?> _translateJina(String text) async {
    try {
      final res = await _dio.post(
        'https://s.jina.ai/translate',
        data: {'text': text, 'source_lang': 'en', 'target_lang': 'zh'},
        options: Options(
          headers: {'Content-Type': 'application/json'},
          receiveTimeout: const Duration(seconds: 6),
        ),
      );
      if (res.statusCode == 200) {
        final data = res.data;
        if (data is Map && data['text'] != null) {
          return data['text'].toString();
        }
        if (data is String) return data;
      }
    } catch (_) {}
    return null;
  }

  /// 引擎3: 有道翻译（网页API）
  Future<String?> _translateYoudao(String text) async {
    try {
      final res = await _dio.post(
        'https://fanyi.youdao.com/translate?&doctype=json&type=AUTO2AUTO',
        data: {'i': text},
        options: Options(
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
          },
          receiveTimeout: const Duration(seconds: 6),
        ),
      );
      if (res.statusCode == 200) {
        final data = res.data;
        if (data is Map && data['translateResult'] != null) {
          final result = data['translateResult'];
          if (result is List && result.isNotEmpty) {
            return result.map((e) => 
              (e as List).map((s) => s['tgt'] ?? '').join('')
            ).join('\n');
          }
        }
      }
    } catch (_) {}
    return null;
  }

  /// 引擎4: MyMemory（免费翻译API）
  Future<String?> _translateMyMemory(String text) async {
    try {
      final encodedText = Uri.encodeComponent(text.length > 500 ? text.substring(0, 500) : text);
      final res = await _dio.get(
        'https://api.mymemory.translated.net/get?q=$encodedText&langpair=en|zh',
        options: Options(receiveTimeout: const Duration(seconds: 6)),
      );
      if (res.statusCode == 200) {
        final data = res.data;
        if (data is Map && data['responseData'] != null) {
          return data['responseData']['translatedText'].toString();
        }
      }
    } catch (_) {}
    return null;
  }

  /// 批量翻译（用于新闻列表）
  Future<Map<String, String>> translateBatch(List<String> texts) async {
    final results = <String, String>{};
    final futures = <Future<void>>[];
    
    for (final text in texts) {
      if (text.isEmpty || !isEnglish(text)) {
        results[text] = text;
        continue;
      }
      if (_cache.containsKey(text)) {
        results[text] = _cache[text]!;
        continue;
      }
      futures.add(translate(text).then((translated) {
        results[text] = translated;
      }));
    }
    
    if (futures.isNotEmpty) {
      await Future.wait(futures);
    }
    return results;
  }

  /// 清空缓存
  void clearCache() {
    _cache.clear();
  }
}
