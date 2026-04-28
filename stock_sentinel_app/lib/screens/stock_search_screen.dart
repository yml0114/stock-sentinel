import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class StockSearchScreen extends StatefulWidget {
  const StockSearchScreen({super.key});

  @override
  State<StockSearchScreen> createState() => _StockSearchScreenState();
}

class _StockSearchScreenState extends State<StockSearchScreen> {
  final _controller = TextEditingController();
  final _api = ApiService();
  List<Map<String, dynamic>> _results = [];
  bool _loading = false;
  Timer? _debounce;

  @override
  void dispose() {
    _controller.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearch(String query) {
    _debounce?.cancel();
    if (query.trim().length < 1) {
      setState(() => _results = []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 300), () => _doSearch(query.trim()));
  }

  Future<void> _doSearch(String q) async {
    setState(() => _loading = true);
    try {
      final results = await _api.searchStocks(q, limit: 30);
      if (mounted) setState(() { _results = results; _loading = false; });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addStock(Map<String, dynamic> stock) async {
    final code = stock['code'] as String;
    final name = stock['name'] as String;
    final market = stock['market'] as String? ?? '';
    try {
      await _api.addStock(code, name: name, market: market);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已添加 $name ($code)'), backgroundColor: Colors.green[700]),
        );
        Navigator.pop(context, true); // 返回true表示有新增
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('添加失败: $e'), backgroundColor: Colors.red[700]),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _controller,
          autofocus: true,
          onChanged: _onSearch,
          style: const TextStyle(color: Colors.white, fontSize: 16),
          decoration: InputDecoration(
            hintText: '搜索A股/港股/美股...',
            hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
            border: InputBorder.none,
            prefixIcon: Icon(Icons.search, color: Colors.white.withOpacity(0.5)),
            suffixIcon: _controller.text.isNotEmpty
                ? IconButton(
                    icon: Icon(Icons.clear, color: Colors.white.withOpacity(0.5)),
                    onPressed: () { _controller.clear(); setState(() => _results = []); },
                  )
                : null,
          ),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _results.isEmpty
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.search, size: 64, color: Colors.white.withOpacity(0.15)),
                      const SizedBox(height: 12),
                      Text(
                        _controller.text.isEmpty ? '输入代码或名称搜索A股/港股/美股' : '未找到匹配结果',
                        style: TextStyle(color: Colors.white.withOpacity(0.4)),
                      ),
                    ],
                  ),
                )
              : ListView.separated(
                  itemCount: _results.length,
                  separatorBuilder: (_, __) => Divider(height: 1, color: Colors.white.withOpacity(0.06)),
                  itemBuilder: (ctx, i) {
                    final stock = _results[i];
                    final code = stock['code'] as String;
                    final name = stock['name'] as String;
                    final market = stock['market'] as String? ?? '';
                    return ListTile(
                      title: Row(
                        children: [
                          Expanded(
                            child: Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
                          ),
                          if (market.isNotEmpty)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: _marketColor(market).withOpacity(0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                _marketLabel(market),
                                style: TextStyle(
                                  color: _marketColor(market),
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                        ],
                      ),
                      subtitle: Text(
                        code,
                        style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
                      ),
                      trailing: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: const Color(0xFF4A90D9).withOpacity(0.2),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text('+ 自选', style: TextStyle(color: Color(0xFF4A90D9), fontSize: 13, fontWeight: FontWeight.w600)),
                      ),
                      onTap: () => _addStock(stock),
                    );
                  },
                ),
    );
  }

  Color _marketColor(String market) {
    switch (market.toUpperCase()) {
      case 'HK': return const Color(0xFFFF6B35);
      case 'US': return const Color(0xFF4A90D9);
      case 'SH':
      case 'SZ':
      case 'A':
      case 'AStock': return const Color(0xFFEF4444);
      default: return const Color(0xFF6B7280);
    }
  }

  String _marketLabel(String market) {
    switch (market.toUpperCase()) {
      case 'HK': return '港股';
      case 'US': return '美股';
      case 'SH':
      case 'SZ':
      case 'A':
      case 'AStock': return 'A股';
      case 'BJ': return '北交所';
      default: return market;
    }
  }
}
