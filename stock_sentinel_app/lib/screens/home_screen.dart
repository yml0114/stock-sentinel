import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/watchlist_provider.dart';
import '../providers/events_provider.dart';
import '../services/ws_service.dart';
import '../widgets/stock_card.dart';
import '../widgets/event_card.dart';
import 'events_screen.dart';
import 'stock_search_screen.dart';
import 'news_screen.dart';

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
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _statItem('自选股', '${wl.stocks.length}'),
              _statItem('今日事件', '${ev.unreadCount}'),
              _statItem('行情', '${wl.quotes.length}'),
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
          return _emptyState(Icons.add_chart, '暂无自选股', '点击右上角 + 添加');
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
          return _emptyState(Icons.notifications_none, '暂无事件', '系统运行后会自动监控');
        }
        return Column(
          children: provider.events.take(3).map((e) => EventCard(event: e)).toList(),
        );
      },
    );
  }

  Widget _emptyState(IconData icon, String title, String subtitle) {
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
}
