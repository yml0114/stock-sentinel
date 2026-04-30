import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../config.dart';
import '../services/api_service.dart';

/// 付费/邀请门控弹窗
/// 两个选项：¥9.9付费（留位置，点击暂无反应）或邀请5人免费解锁
class PaywallDialog extends StatelessWidget {
  final VoidCallback? onUnlocked;
  const PaywallDialog({super.key, this.onUnlocked});

  /// 检查是否需要显示付费墙（未付费且未登录时弹出）
  static Future<bool> shouldShow() async {
    if (!AppConfig.isLoggedIn) return false;
    if (AppConfig.isPremium) return false;
    // 检查服务端状态
    try {
      final api = ApiService();
      final status = await api.getInviteStatus();
      final data = status['data'];
      if (data != null && data['isPremium'] == true) {
        AppConfig.savePremium(true);
        return false;
      }
    } catch (_) {}
    return true;
  }

  static Future<void> showIfNeeded(BuildContext context) async {
    if (await shouldShow()) {
      if (context.mounted) {
        showDialog(
          context: context,
          barrierDismissible: true,
          builder: (_) => const PaywallDialog(),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: const Color(0xFF16213E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 标题
            Container(
              width: 60, height: 60,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF4A90D9), Color(0xFF7C4DFF)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(Icons.workspace_premium, size: 32, color: Colors.white),
            ),
            const SizedBox(height: 16),
            const Text(
              '解锁完整功能',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 8),
            Text(
              'AI诊断 · 研报解读 · 实时监控',
              style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.6)),
            ),
            const SizedBox(height: 24),

            // 方案1：付费
            _OptionCard(
              icon: Icons.payment,
              title: '¥9.9 一次性买断',
              subtitle: '永久解锁所有功能',
              gradient: const [Color(0xFFFFD700), Color(0xFFFFA500)],
              onTap: () {
                // TODO: 接入支付SDK
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('支付功能开发中，敬请期待...'), duration: Duration(seconds: 2)),
                );
              },
            ),
            const SizedBox(height: 12),

            // 方案2：邀请
            _OptionCard(
              icon: Icons.people,
              title: '邀请5位好友免费解锁',
              subtitle: '分享给朋友，一起看行情',
              gradient: const [Color(0xFF4A90D9), Color(0xFF7C4DFF)],
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => InvitePage(onUnlocked: onUnlocked)),
                );
              },
            ),
            const SizedBox(height: 16),

            // 底部小字
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(
                '稍后再说',
                style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OptionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final List<Color> gradient;
  final VoidCallback onTap;

  const _OptionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.gradient,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: gradient[0].withOpacity(0.3)),
            color: gradient[0].withOpacity(0.08),
          ),
          child: Row(
            children: [
              Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: gradient),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: Colors.white, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.white)),
                    const SizedBox(height: 3),
                    Text(subtitle, style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5))),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: Colors.white.withOpacity(0.3)),
            ],
          ),
        ),
      ),
    );
  }
}


/// 邀请页面 — 显示邀请码 + 邀请进度 + 好友列表
class InvitePage extends StatefulWidget {
  final VoidCallback? onUnlocked;
  const InvitePage({super.key, this.onUnlocked});

  @override
  State<InvitePage> createState() => _InvitePageState();
}

class _InvitePageState extends State<InvitePage> {
  String _inviteCode = '';
  int _inviteCount = 0;
  bool _loading = true;
  String _error = '';
  List<Map<String, dynamic>> _friends = [];

  // 输入邀请码
  final _codeController = TextEditingController();
  bool _redeeming = false;
  String _redeemError = '';

  @override
  void initState() {
    super.initState();
    _loadStatus();
  }

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _loadStatus() async {
    setState(() { _loading = true; _error = ''; });
    try {
      final api = ApiService();
      final status = await api.getInviteStatus();
      final data = status['data'];
      setState(() {
        _inviteCode = data['inviteCode'] ?? '';
        _inviteCount = data['inviteCount'] ?? 0;
      });
      // 同步服务端premium状态
      if (data['isPremium'] == true) {
        AppConfig.savePremium(true);
      }
      // 加载好友列表
      final friends = await api.getInviteFriends();
      setState(() => _friends = friends);
    } catch (e) {
      setState(() => _error = '加载失败，请检查网络');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _redeem() async {
    final code = _codeController.text.trim();
    if (code.isEmpty || code.length < 4) {
      setState(() => _redeemError = '请输入有效邀请码');
      return;
    }
    setState(() { _redeeming = true; _redeemError = ''; });
    try {
      final api = ApiService();
      final result = await api.redeemInviteCode(code);
      if (result['code'] == 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(result['data']['message'] ?? '邀请码使用成功'), backgroundColor: const Color(0xFF10B981)),
        );
        _codeController.clear();
        await _loadStatus();
        // 检查是否解锁
        if (_inviteCount >= 5 && mounted) {
          AppConfig.savePremium(true);
          widget.onUnlocked?.call();
        }
      } else {
        setState(() => _redeemError = result['message'] ?? '兑换失败');
      }
    } catch (e) {
      setState(() => _redeemError = '网络错误');
    } finally {
      if (mounted) setState(() => _redeeming = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = _inviteCount / 5;
    return Scaffold(
      backgroundColor: const Color(0xFF0D0D1A),
      appBar: AppBar(
        title: const Text('邀请好友'),
        backgroundColor: const Color(0xFF0D0D1A),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadStatus,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  // ── 进度卡片 ──
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF1A2744), Color(0xFF16213E)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: Colors.white.withOpacity(0.08)),
                    ),
                    child: Column(
                      children: [
                        const Text('邀请进度', style: TextStyle(color: Colors.grey, fontSize: 13)),
                        const SizedBox(height: 12),
                        Text(
                          '$_inviteCount / 5',
                          style: const TextStyle(fontSize: 42, fontWeight: FontWeight.bold, color: Color(0xFF4A90D9)),
                        ),
                        const SizedBox(height: 12),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: LinearProgressIndicator(
                            value: progress.clamp(0.0, 1.0),
                            minHeight: 10,
                            backgroundColor: Colors.white.withOpacity(0.1),
                            valueColor: AlwaysStoppedAnimation<Color>(
                              _inviteCount >= 5 ? const Color(0xFF10B981) : const Color(0xFF4A90D9),
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          _inviteCount >= 5
                              ? '🎉 恭喜！已解锁完整功能'
                              : '再邀请 ${5 - _inviteCount} 人即可免费解锁',
                          style: TextStyle(
                            color: _inviteCount >= 5 ? const Color(0xFF10B981) : Colors.white.withOpacity(0.7),
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // ── 我的邀请码 ──
                  const Text('我的邀请码', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  GestureDetector(
                    onTap: () {
                      Clipboard.setData(ClipboardData(text: _inviteCode));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('邀请码已复制'), duration: Duration(seconds: 1)),
                      );
                    },
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
                      decoration: BoxDecoration(
                        color: const Color(0xFF16213E),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFF4A90D9).withOpacity(0.3)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            _inviteCode,
                            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFF4A90D9), letterSpacing: 6),
                          ),
                          const SizedBox(width: 12),
                          Icon(Icons.copy, color: Colors.white.withOpacity(0.4), size: 20),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Center(
                    child: Text(
                      '分享邀请码给朋友，朋友注册后输入即可',
                      style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.4)),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // ── 输入邀请码 ──
                  const Text('使用邀请码', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _codeController,
                          textCapitalization: TextCapitalization.characters,
                          style: const TextStyle(color: Colors.white, letterSpacing: 4, fontSize: 18),
                          decoration: InputDecoration(
                            hintText: '输入邀请码',
                            hintStyle: TextStyle(color: Colors.white.withOpacity(0.3), letterSpacing: 1, fontSize: 14),
                            filled: true,
                            fillColor: const Color(0xFF16213E),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                              borderSide: BorderSide.none,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      SizedBox(
                        height: 48,
                        child: ElevatedButton(
                          onPressed: _redeeming ? null : _redeem,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF4A90D9),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                          child: _redeeming
                              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('兑换', style: TextStyle(color: Colors.white)),
                        ),
                      ),
                    ],
                  ),
                  if (_redeemError.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(_redeemError, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13)),
                  ],
                  const SizedBox(height: 24),

                  // ── 邀请的好友 ──
                  if (_friends.isNotEmpty) ...[
                    Text('已邀请的好友 (${_friends.length})', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    ..._friends.map((f) => Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFF16213E),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 36, height: 36,
                            decoration: BoxDecoration(
                              color: const Color(0xFF4A90D9).withOpacity(0.2),
                              shape: BoxShape.circle,
                            ),
                            child: Center(
                              child: Text(
                                (f['nickname'] ?? '?').toString().isNotEmpty ? (f['nickname'] ?? '?')[0] : '?',
                                style: const TextStyle(color: Color(0xFF4A90D9), fontWeight: FontWeight.bold),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(f['nickname'] ?? '', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
                                Text(f['phone'] ?? '', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12)),
                              ],
                            ),
                          ),
                          const Icon(Icons.check_circle, color: Color(0xFF10B981), size: 20),
                        ],
                      ),
                    )),
                  ],

                  if (_error.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(_error, style: const TextStyle(color: Color(0xFFEF4444))),
                  ],
                ],
              ),
            ),
    );
  }
}
