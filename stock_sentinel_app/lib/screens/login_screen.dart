import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api_service.dart';
import '../config.dart';

class LoginScreen extends StatefulWidget {
  final VoidCallback onLoginSuccess;
  const LoginScreen({super.key, required this.onLoginSuccess});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();
  bool _codeSent = false;
  bool _loading = false;
  String _error = '';
  int _countdown = 0;
  String _devCode = ''; // 开发模式验证码

  @override
  void dispose() {
    _phoneController.dispose();
    _codeController.dispose();
    super.dispose();
  }

  void _startCountdown() {
    setState(() => _countdown = 60);
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return false;
      setState(() => _countdown--);
      return _countdown > 0;
    });
  }

  Future<void> _sendCode() async {
    final phone = _phoneController.text.trim();
    if (phone.length != 11) {
      setState(() => _error = '请输入11位手机号');
      return;
    }
    setState(() { _loading = true; _error = ''; _devCode = ''; });
    try {
      final api = ApiService();
      final result = await api.sendCode(phone);
      if (result['code'] == 0) {
        // 服务端会返回验证码（开发模式或ntfy失败时）
        final data = result['data'] ?? {};
        final serverCode = data['code'] ?? '';
        setState(() {
          _codeSent = true;
          _devCode = serverCode;
        });
        _startCountdown();
      } else {
        setState(() => _error = result['message'] ?? '发送失败');
      }
    } catch (e) {
      setState(() => _error = '网络错误，请检查连接');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _login() async {
    final phone = _phoneController.text.trim();
    final code = _codeController.text.trim();
    if (code.length != 6) {
      setState(() => _error = '请输入6位验证码');
      return;
    }
    setState(() { _loading = true; _error = ''; });
    try {
      final api = ApiService();
      final result = await api.login(phone, code);
      if (result['code'] == 0) {
        final token = result['data']['token'] as String;
        final user = result['data']['user'];
        await AppConfig.saveToken(token);
        await AppConfig.saveUser(user);
        widget.onLoginSuccess();
      } else {
        setState(() => _error = result['message'] ?? '登录失败');
      }
    } catch (e) {
      setState(() => _error = '网络错误');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      backgroundColor: const Color(0xFF0D0D1A),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: MediaQuery.of(context).size.height -
                  MediaQuery.of(context).padding.top -
                  MediaQuery.of(context).padding.bottom - 48,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Logo
                Container(
                  width: 80, height: 80,
                  decoration: BoxDecoration(
                    color: const Color(0xFF16213E),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Icon(Icons.show_chart, size: 40, color: Color(0xFF4A90D9)),
                ),
                const SizedBox(height: 16),
                const Text('金融哨兵', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
                const SizedBox(height: 8),
                const Text('登录后可同步自选股和设置', style: TextStyle(fontSize: 14, color: Colors.grey)),
                const SizedBox(height: 48),

                // 手机号输入
                TextField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  maxLength: 11,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: '手机号',
                    hintStyle: const TextStyle(color: Colors.grey),
                    prefixIcon: const Icon(Icons.phone_android, color: Colors.grey),
                    filled: true,
                    fillColor: const Color(0xFF16213E),
                    counterText: '',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // 验证码输入 + 发送按钮
                if (_codeSent) ...[
                  // 验证码提示卡片
                  if (_devCode.isNotEmpty) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4A90D9).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFF4A90D9).withOpacity(0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.info_outline, color: Color(0xFF4A90D9), size: 20),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('您的验证码', style: TextStyle(color: Color(0xFF4A90D9), fontSize: 12)),
                                const SizedBox(height: 4),
                                Row(
                                  children: [
                                    Text(_devCode, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: 6)),
                                    const SizedBox(width: 12),
                                    GestureDetector(
                                      onTap: () {
                                        Clipboard.setData(ClipboardData(text: _devCode));
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
                                        );
                                        // 自动填入
                                        _codeController.text = _devCode;
                                        setState(() {});
                                      },
                                      child: Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFF4A90D9).withOpacity(0.2),
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: const Text('复制', style: TextStyle(color: Color(0xFF4A90D9), fontSize: 12)),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _codeController,
                          keyboardType: TextInputType.number,
                          maxLength: 6,
                          style: const TextStyle(color: Colors.white, letterSpacing: 8, fontSize: 20),
                          decoration: InputDecoration(
                            hintText: '验证码',
                            hintStyle: const TextStyle(color: Colors.grey, letterSpacing: 2, fontSize: 14),
                            prefixIcon: const Icon(Icons.lock_outline, color: Colors.grey),
                            filled: true,
                            fillColor: const Color(0xFF16213E),
                            counterText: '',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                              borderSide: BorderSide.none,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      TextButton(
                        onPressed: _countdown > 0 ? null : _sendCode,
                        child: Text(
                          _countdown > 0 ? '${_countdown}s' : '重新发送',
                          style: TextStyle(color: _countdown > 0 ? Colors.grey : const Color(0xFF4A90D9)),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity, height: 48,
                    child: ElevatedButton(
                      onPressed: _loading ? null : _login,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF4A90D9),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _loading
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('登录', style: TextStyle(fontSize: 16, color: Colors.white)),
                    ),
                  ),
                ] else ...[
                  SizedBox(
                    width: double.infinity, height: 48,
                    child: ElevatedButton(
                      onPressed: _loading ? null : _sendCode,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF4A90D9),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _loading
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('获取验证码', style: TextStyle(fontSize: 16, color: Colors.white)),
                    ),
                  ),
                ],

                // 错误信息
                if (_error.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Text(_error, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13)),
                ],

                const SizedBox(height: 24),
                // 跳过登录
                TextButton(
                  onPressed: () {
                    Navigator.of(context).pop();
                  },
                  child: const Text('先逛逛，稍后登录', style: TextStyle(color: Colors.grey, fontSize: 13)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
