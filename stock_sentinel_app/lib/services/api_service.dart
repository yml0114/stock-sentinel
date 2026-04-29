import 'package:dio/dio.dart';
import '../config.dart';
import '../models/stock.dart';
import '../models/quote.dart';
import '../models/event.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;

  late final Dio _dio;

  ApiService._internal() {
    _dio = Dio(BaseOptions(
      baseUrl: AppConfig.apiBase,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ));

    // 自动附加Token
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (AppConfig.token != null) {
          options.headers['Authorization'] = 'Bearer ${AppConfig.token}';
        }
        handler.next(options);
      },
    ));
  }

  dynamic _extract(Response res) {
    final body = res.data;
    if (body is Map && body.containsKey('data')) {
      return body['data'];
    }
    return body;
  }

  // ── 认证 ──

  Future<Map<String, dynamic>> sendCode(String phone) async {
    final res = await _dio.post('/auth/send-code', data: {'phone': phone});
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> login(String phone, String code) async {
    final res = await _dio.post('/auth/login', data: {'phone': phone, 'code': code});
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getMe() async {
    final res = await _dio.get('/auth/me');
    return res.data as Map<String, dynamic>;
  }

  Future<void> updateSettings(Map<String, dynamic> settings) async {
    await _dio.post('/auth/settings', data: {'settings': settings});
  }

  // ── 自选股 ──

  Future<List<Stock>> getWatchlist() async {
    final res = await _dio.get('/watchlist');
    final data = _extract(res) as List;
    return data.map((e) => Stock.fromJson(e)).toList();
  }

  Future<void> addStock(String code, {String? name, String? market}) async {
    await _dio.post('/watchlist', data: {
      'code': code,
      if (name != null) 'name': name,
      if (market != null && market.isNotEmpty) 'market': market,
    });
  }

  Future<void> removeStock(String code) async {
    await _dio.delete('/watchlist/$code');
  }

  // ── 行情 ──

  Future<List<Quote>> getQuotes() async {
    final res = await _dio.get('/quotes');
    final data = _extract(res) as List;
    return data.map((e) => Quote.fromJson(e)).toList();
  }

  // ── 事件 ──

  Future<List<SentinelEvent>> getEvents({String? code, int limit = 50}) async {
    final params = <String, dynamic>{'limit': limit};
    if (code != null) params['code'] = code;
    final res = await _dio.get('/events', queryParameters: params);
    final data = _extract(res) as List;
    return data.map((e) => SentinelEvent.fromJson(e)).toList();
  }

  // ── 新闻 ──

  Future<List<Map<String, dynamic>>> getNewsRaw({int limit = 80}) async {
    final res = await _dio.get('/news/raw', queryParameters: {'limit': limit},
      options: Options(receiveTimeout: const Duration(seconds: 60)));
    final data = _extract(res) as List;
    return data.cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> getNewsFiltered() async {
    final res = await _dio.get('/news/filtered');
    final data = _extract(res) as List;
    return data.cast<Map<String, dynamic>>();
  }

  // ── 状态 ──

  Future<Map<String, dynamic>> getStatus() async {
    final res = await _dio.get('/status');
    return _extract(res) as Map<String, dynamic>;
  }

  // ── 股票搜索 ──

  Future<List<Map<String, dynamic>>> searchStocks(String query, {int limit = 20}) async {
    final res = await _dio.get('/search', queryParameters: {'q': query, 'limit': limit});
    final data = _extract(res) as List;
    return data.cast<Map<String, dynamic>>();
  }

  // ── K线数据 ──

  Future<List<Map<String, dynamic>>> getKline(String code, {String period = 'daily', int days = 120, String market = ''}) async {
    final params = <String, dynamic>{'period': period, 'days': days};
    if (market.isNotEmpty) params['market'] = market;
    final res = await _dio.get('/kline/$code', queryParameters: params);
    final data = _extract(res) as List;
    return data.cast<Map<String, dynamic>>();
  }

  // ── 研报 ──

  Future<Map<String, dynamic>> getResearch(String code, {int limit = 10}) async {
    final res = await _dio.get('/research/$code', queryParameters: {'limit': limit});
    return _extract(res) as Map<String, dynamic>;
  }

  // ── 个股画像 ──

  Future<Map<String, dynamic>> getProfile(String code, {double price = 0}) async {
    final res = await _dio.get('/profile/$code', queryParameters: {'price': price});
    return _extract(res) as Map<String, dynamic>;
  }

  // ── 个股画像 AI 分析 ──

  Future<Map<String, dynamic>> getProfileAI(String code, {double price = 0}) async {
    final res = await _dio.get('/profile/$code/ai', queryParameters: {'price': price});
    return _extract(res) as Map<String, dynamic>;
  }

  // ── 千股千评 ──

  Future<Map<String, dynamic>> getComment(String code) async {
    final res = await _dio.get('/comment/$code');
    return _extract(res) as Map<String, dynamic>;
  }

  // ── 技术指标 ──

  Future<Map<String, dynamic>> getIndicators(String code, {String period = 'daily', int days = 120, String market = ''}) async {
    final params = <String, dynamic>{'period': period, 'days': days};
    if (market.isNotEmpty) params['market'] = market;
    final res = await _dio.get('/indicators/$code', queryParameters: params);
    return _extract(res) as Map<String, dynamic>;
  }

  // ── AI诊断 ──

  Future<Map<String, dynamic>> getDiagnose(String code, {String market = '', String period = 'daily', int days = 120}) async {
    final params = <String, dynamic>{'period': period, 'days': days};
    if (market.isNotEmpty) params['market'] = market;
    final res = await _dio.get('/diagnose/$code', queryParameters: params,
      options: Options(receiveTimeout: const Duration(seconds: 60)));
    return _extract(res) as Map<String, dynamic>;
  }

  // ── 分析师 ──

  Future<List<dynamic>> getAnalysts({int limit = 20}) async {
    final res = await _dio.get('/analysts', queryParameters: {'limit': limit});
    return _extract(res) as List;
  }

  // ── 文章正文抓取 ──

  Future<Map<String, dynamic>> getArticle(String url) async {
    final res = await _dio.get('/article', queryParameters: {'url': url},
      options: Options(receiveTimeout: const Duration(seconds: 20)));
    return _extract(res) as Map<String, dynamic>;
  }
}
