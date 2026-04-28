import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/event.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';

class EventsProvider extends ChangeNotifier {
  final ApiService _api = ApiService();
  final WsService _ws = WsService();

  List<SentinelEvent> _events = [];
  int _unreadCount = 0;
  bool _loading = false;
  StreamSubscription? _wsSubscription;

  List<SentinelEvent> get events => _events;
  int get unreadCount => _unreadCount;
  bool get loading => _loading;

  /// 刷新事件
  Future<void> refresh({String? code, int limit = 50}) async {
    _loading = true;
    notifyListeners();

    try {
      _events = await _api.getEvents(code: code, limit: limit);
    } catch (e) {
      print('[EventsProvider] refresh error: $e');
    }

    _loading = false;
    notifyListeners();
  }

  /// 标记已读
  void markRead() {
    _unreadCount = 0;
    notifyListeners();
  }

  /// 监听WebSocket实时事件
  void listenWebSocket() {
    _wsSubscription?.cancel();
    _ws.connect();
    _wsSubscription = _ws.eventStream.listen((data) {
      try {
        final event = SentinelEvent.fromJson(data);
        _events.insert(0, event);
        _unreadCount++;
        notifyListeners();
      } catch (e) {
        print('[EventsProvider] ws parse error: $e');
      }
    });
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}
