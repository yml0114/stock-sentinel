import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config.dart';

class WsService {
  static final WsService _instance = WsService._internal();
  factory WsService() => _instance;

  WebSocketChannel? _channel;
  final _eventController = StreamController<Map<String, dynamic>>.broadcast();
  Timer? _reconnectTimer;
  Timer? _heartbeatTimer;
  bool _disposed = false;

  /// 事件流
  Stream<Map<String, dynamic>> get eventStream => _eventController.stream;

  WsService._internal();

  /// 连接WebSocket
  void connect() {
    if (_disposed) return;
    _disconnect();

    try {
      final uri = Uri.parse(AppConfig.wsUrl);
      _channel = WebSocketChannel.connect(uri);
      _channel!.stream.listen(
        (data) {
          try {
            final json = jsonDecode(data.toString()) as Map<String, dynamic>;
            _eventController.add(json);
          } catch (e) {
            print('[WsService] parse error: $e');
          }
        },
        onDone: () {
          print('[WsService] connection closed');
          _scheduleReconnect();
        },
        onError: (error) {
          print('[WsService] error: $error');
          _scheduleReconnect();
        },
      );

      // 心跳
      _heartbeatTimer?.cancel();
      _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
        _send({'type': 'ping'});
      });

      print('[WsService] connected to ${AppConfig.wsUrl}');
    } catch (e) {
      print('[WsService] connect failed: $e');
      _scheduleReconnect();
    }
  }

  /// 发送消息
  void _send(Map<String, dynamic> data) {
    try {
      _channel?.sink.add(jsonEncode(data));
    } catch (e) {
      print('[WsService] send error: $e');
    }
  }

  /// 断开连接
  void _disconnect() {
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
  }

  /// 计划重连
  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), () {
      print('[WsService] attempting reconnect...');
      connect();
    });
  }

  /// 销毁
  void dispose() {
    _disposed = true;
    _disconnect();
    _eventController.close();
  }
}
