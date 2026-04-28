import 'package:flutter/foundation.dart';
import '../models/stock.dart';
import '../models/quote.dart';
import '../services/api_service.dart';

class WatchlistProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  List<Stock> _stocks = [];
  List<Quote> _quotes = [];
  bool _loading = false;
  String? _error;

  List<Stock> get stocks => _stocks;
  List<Quote> get quotes => _quotes;
  bool get loading => _loading;
  String? get error => _error;

  /// 根据代码获取行情
  Quote? getQuote(String code) {
    try {
      return _quotes.firstWhere((q) => q.code == code);
    } catch (_) {
      return null;
    }
  }

  /// 刷新自选股和行情
  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        _api.getWatchlist(),
        _api.getQuotes(),
      ]);
      _stocks = results[0] as List<Stock>;
      _quotes = results[1] as List<Quote>;
    } catch (e) {
      _error = e.toString();
    }

    _loading = false;
    notifyListeners();
  }

  /// 添加自选股
  Future<bool> addStock(String code, {String? name}) async {
    try {
      await _api.addStock(code, name: name);
      await refresh();
      return true;
    } catch (e) {
      return false;
    }
  }

  /// 删除自选股
  Future<bool> removeStock(String code) async {
    try {
      await _api.removeStock(code);
      _stocks.removeWhere((s) => s.code == code);
      _quotes.removeWhere((q) => q.code == code);
      notifyListeners();
      return true;
    } catch (e) {
      return false;
    }
  }
}
