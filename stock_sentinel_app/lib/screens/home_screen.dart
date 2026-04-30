import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config.dart';
import '../providers/watchlist_provider.dart';
import '../providers/events_provider.dart';
import '../services/ws_service.dart';
import '../widgets/stock_card.dart';
import '../widgets/event_card.dart';
import 'events_screen.dart';
import 'stock_search_screen.dart';
import 'news_screen.dart';
import 'login_screen.dart';
import '../widgets/paywall_dialog.dart';  // also exports InvitePage

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      context.read<WatchlistProvider>().refresh();
      context.read<EventsProvider>().refresh();
      // 付费墙已隐藏（enablePremium=false）
    });
    WsService().eventStream.listen((event) {
      if (event['type'] == 'new_event') {
        context.read<EventsProvider>().refresh();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: [
          _buildHomePage(),
          const NewsScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        backgroundColor: const Color(0xFF0D0D1A),
        selectedItemColor: const Color(0xFF4A90D9),
        unselectedItemColor: Colors.white.withOpacity(0.4),
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: '自选'),
          BottomNavigationBarItem(icon: Icon(Icons.article), label: '新闻'),
        ],
      ),
    );
  }

  Widget _buildHomePage() {
    return RefreshIndicator(
      onRefresh: () async {
        await context.read<WatchlistProvider>().refresh();
        await context.read<EventsProvider>().refresh();
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── 状态卡片 ──
          _buildStatusCard(),
          const SizedBox(height: 20),

          // ── 自选股 ──
          _buildSectionHeader('自选股', onAdd: _openSearch),
          const SizedBox(height: 8),
          _buildWatchlist(),
          const SizedBox(height: 20),

          // ── 最新事件 ──
          _buildSectionHeader('最新事件', onViewAll: () {
            Navigator.push(context, MaterialPageRoute(builder: (_) => const EventsScreen()));
          }),
          const SizedBox(height: 8),
          _buildEventsPreview(),
        ],
      ),
    );
  }

  Widget _buildStatusCard() {
    return Consumer2<WatchlistProvider, EventsProvider>(
      builder: (ctx, wl, ev, _) {
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF1A1A2E),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withOpacity(0.08)),
          ),
          child: Row(
            children: [
              // 用户头像/登录入口
              GestureDetector(
                onTap: () => _openLogin(ctx),
                child: Container(
                  width: 44, height: 44,
                  decoration: BoxDecoration(
                    color: AppConfig.isLoggedIn
                        ? const Color(0xFF4A90D9).withOpacity(0.2)
                        : Colors.white.withOpacity(0.06),
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: AppConfig.isLoggedIn
                        ? Text(
                            AppConfig.nickname.isNotEmpty ? AppConfig.nickname[0] : '?',
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF4A90D9)),
                          )
                        : Icon(Icons.person_outline, size: 22, color: Colors.white.withOpacity(0.4)),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              // 统计数据
              Expanded(
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _statItem('自选股', '${wl.stocks.length}'),
                    _statItem('今日事件', '${ev.unreadCount}'),
                    _statItem('行情', '${wl.quotes.length}'),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _statItem(String label, String value) {
    return Column(
      children: [
        Text(value, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF4A90D9))),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5))),
      ],
    );
  }

  Widget _buildSectionHeader(String title, {VoidCallback? onAdd, VoidCallback? onViewAll}) {
    return Row(
      children: [
        Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const Spacer(),
        if (onAdd != null)
          IconButton(icon: const Icon(Icons.add_circle_outline, color: Color(0xFF4A90D9)), onPressed: onAdd),
        if (onViewAll != null)
          TextButton(onPressed: onViewAll, child: const Text('查看全部')),
      ],
    );
  }

  Widget _buildWatchlist() {
    return Consumer<WatchlistProvider>(
      builder: (ctx, provider, _) {
        if (provider.loading && provider.stocks.isEmpty) {
          return const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()));
        }
        if (provider.stocks.isEmpty) {
          final hasError = provider.error != null;
          return _emptyState(
            hasError ? Icons.cloud_off : Icons.add_chart,
            hasError ? '加载失败' : '暂无自选股',
            hasError ? '网络连接异常，请检查网络' : '点击右上角 + 添加',
            onRetry: hasError ? () => provider.refresh() : null,
          );
        }
        return Column(
          children: provider.stocks.map((stock) {
            final quote = provider.getQuote(stock.code);
            return Dismissible(
              key: Key(stock.code),
              direction: DismissDirection.endToStart,
              background: Container(
                alignment: Alignment.centerRight,
                padding: const EdgeInsets.only(right: 20),
                color: Colors.red.shade700,
                child: const Icon(Icons.delete, color: Colors.white),
              ),
              confirmDismiss: (_) async {
                return await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('删除自选'),
                    content: Text('确定删除 ${stock.name} (${stock.code})？'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
                      TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('删除', style: TextStyle(color: Colors.red))),
                    ],
                  ),
                );
              },
              onDismissed: (_) {
                provider.removeStock(stock.code);
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('已删除 ${stock.name}')));
              },
              child: StockCard(
                stock: stock,
                quote: quote,
              ),
            );
          }).toList(),
        );
      },
    );
  }

  Widget _buildEventsPreview() {
    return Consumer<EventsProvider>(
      builder: (ctx, provider, _) {
        if (provider.loading && provider.events.isEmpty) {
          return const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()));
        }
        if (provider.events.isEmpty) {
          return _emptyState(
            Icons.notifications_none,
            '暂无事件',
            '系统运行后会自动监控',
            onRetry: () => provider.refresh(),
          );
        }
        return Column(
          children: provider.events.take(3).map((e) => EventCard(event: e)).toList(),
        );
      },
    );
  }

  Widget _emptyState(IconData icon, String title, String subtitle, {VoidCallback? onRetry}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 40),
      alignment: Alignment.center,
      child: Column(
        children: [
          Icon(icon, size: 48, color: Colors.white.withOpacity(0.15)),
          const SizedBox(height: 12),
          Text(title, style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 16)),
          const SizedBox(height: 4),
          Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.25), fontSize: 13)),
          if (onRetry != null) ...[
            const SizedBox(height: 16),
            GestureDetector(
              onTap: onRetry,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0xFF4A90D9).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF4A90D9).withOpacity(0.3)),
                ),
                child: const Text('重试', style: TextStyle(color: Color(0xFF4A90D9), fontSize: 14, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _openSearch() async {
    final added = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const StockSearchScreen()),
    );
    if (added == true && mounted) {
      context.read<WatchlistProvider>().refresh();
    }
  }

  Future<void> _openLogin(BuildContext ctx) async {
    if (AppConfig.isLoggedIn) {
      // 已登录 → 显示用户信息/邀请/退出
      final action = await showDialog<String>(
        context: ctx,
        builder: (dCtx) => SimpleDialog(
          backgroundColor: const Color(0xFF16213E),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text(AppConfig.nickname, style: const TextStyle(color: Colors.white)),
          children: [
            // 手机号
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text(
                '手机号: ${AppConfig.user?['phone'] ?? ''}',
                style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
              ),
            ),
            const SizedBox(height: 8),
            // 邀请好友（已隐藏 enablePremium=false）
            if (AppConfig.enablePremium)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(dCtx, 'invite'),
                child: Row(
                  children: [
                    const Icon(Icons.people, color: Color(0xFF4A90D9), size: 20),
                    const SizedBox(width: 12),
                    const Text('邀请好友', style: TextStyle(color: Colors.white)),
                    if (AppConfig.isPremium) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFF10B981).withOpacity(0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('PRO', style: TextStyle(color: Color(0xFF10B981), fontSize: 10, fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ],
                ),
              ),
            // 退出登录
            SimpleDialogOption(
              onPressed: () => Navigator.pop(dCtx, 'logout'),
              child: const Row(
                children: [
                  Icon(Icons.logout, color: Color(0xFFEF4444), size: 20),
                  SizedBox(width: 12),
                  Text('退出登录', style: TextStyle(color: Color(0xFFEF4444))),
                ],
              ),
            ),
          ],
        ),
      );
      if (action == 'logout' && mounted) {
        await AppConfig.logout();
        setState(() {});
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已退出登录')));
      } else if (action == 'invite' && mounted && AppConfig.enablePremium) {
        Navigator.push(ctx, MaterialPageRoute(builder: (_) => const InvitePage()));
      }
      return;
    }
    // 未登录 → 打开登录页
    await Navigator.push(
      ctx,
      MaterialPageRoute(
        builder: (_) => LoginScreen(
          onLoginSuccess: () {
            Navigator.pop(ctx);
            setState(() {});
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('欢迎, ${AppConfig.nickname}!')),
            );
          },
        ),
      ),
    );
  }
}
