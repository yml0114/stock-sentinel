import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/event.dart';
import '../widgets/kline_chart.dart';
import '../widgets/trend_chart.dart';
import '../widgets/event_card.dart';

class StockDetailScreen extends StatefulWidget {
  final String code;
  final String name;
  final String market;
  const StockDetailScreen({super.key, required this.code, required this.name, this.market = ''});

  @override
  State<StockDetailScreen> createState() => _StockDetailScreenState();
}

class _StockDetailScreenState extends State<StockDetailScreen> {
  final _api = ApiService();
  List<Map<String, dynamic>> _klineData = [];
  Map<String, dynamic> _trendData = {};
  Map<String, dynamic> _profile = {};
  Map<String, dynamic> _comment = {};
  List<SentinelEvent> _events = [];
  bool _loadingKline = true;
  bool _loadingTrend = true;
  bool _loadingProfile = true;
  double _currentPrice = 0;
  String _period = 'daily';
  int _days = 120;
  String _currentPeriodLabel = '日K';
  String _currencySymbol = '¥';
  Map<String, dynamic> _indicators = {};
  bool _loadingDiagnose = false;

  // 分时/K线切换
  bool _showTrend = true; // 默认显示分时
  Timer? _refreshTimer;
  bool _isTradingHours = false;

  @override
  void initState() {
    super.initState();
    _updateCurrency();
    _loadAll();
    _checkTradingHours();
    _startAutoRefresh();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  bool _checkTradingHours() {
    final now = DateTime.now();
    // 周一到周五
    if (now.weekday > 5) {
      _isTradingHours = false;
      return false;
    }
    final hour = now.hour;
    final minute = now.minute;
    final t = hour * 60 + minute;
    // 9:15 - 11:30, 13:00 - 15:00
    _isTradingHours = (t >= 9 * 60 + 15 && t <= 11 * 60 + 30) ||
                      (t >= 13 * 60 && t <= 15 * 60);
    return _isTradingHours;
  }

  void _startAutoRefresh() {
    _refreshTimer?.cancel();
    // 每5秒刷新行情和分时数据（交易时段）
    _refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (_checkTradingHours() && mounted) {
        _loadTrend(silent: true);
        _loadProfile();
      }
    });
  }

  Future<void> _loadTrend({bool silent = false}) async {
    if (!silent) setState(() => _loadingTrend = true);
    try {
      final data = await _api.getTrend(widget.code, market: widget.market);
      if (mounted) setState(() {
        _trendData = data;
        _loadingTrend = false;
        // 更新实时价格
        final rt = data['realtime'] as Map<String, dynamic>? ?? {};
        _currentPrice = (rt['price'] as num?)?.toDouble() ?? _currentPrice;
      });
    } catch (e) {
      if (mounted && !silent) setState(() => _loadingTrend = false);
    }
  }

  void _updateCurrency() {
    switch (widget.market.toUpperCase()) {
      case 'HK':
        _currencySymbol = 'HK\$';
        break;
      case 'US':
        _currencySymbol = '\$';
        break;
      default:
        _currencySymbol = '¥';
    }
  }

  Future<void> _loadAll() async {
    await Future.wait([_loadTrend(), _loadKline(), _loadProfile(), _loadEvents(), _loadIndicators()]);
  }

  Future<void> _loadKline() async {
    setState(() => _loadingKline = true);
    try {
      final data = await _api.getKline(widget.code, period: _period, days: _days, market: widget.market);
      if (mounted) setState(() { _klineData = data; _loadingKline = false; });
    } catch (e) {
      if (mounted) setState(() => _loadingKline = false);
    }
  }

  Future<void> _loadProfile() async {
    setState(() => _loadingProfile = true);
    try {
      final profile = await _api.getProfile(widget.code);
      final comment = await _api.getComment(widget.code);
      if (mounted) setState(() {
        _profile = profile;
        _comment = comment;
        _currentPrice = (comment['price'] as num?)?.toDouble() ?? 0;
        _loadingProfile = false;
      });
    } catch (e) {
      if (mounted) setState(() => _loadingProfile = false);
    }
  }

  Future<void> _loadEvents() async {
    try {
      final events = await _api.getEvents(code: widget.code, limit: 20);
      if (mounted) setState(() => _events = events);
    } catch (_) {}
  }

  Future<void> _loadIndicators() async {
    try {
      final data = await _api.getIndicators(widget.code, period: _period, days: _days, market: widget.market);
      if (mounted) setState(() => _indicators = data);
    } catch (_) {}
  }

  void _switchPeriod(String period, int days, String label) {
    setState(() {
      _period = period;
      _days = days;
      _currentPeriodLabel = label;
    });
    _loadKline();
  }

  Future<void> _showDiagnosis() async {
    setState(() => _loadingDiagnose = true);

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E1E2E),
        title: Row(
          children: [
            const Icon(Icons.analytics, color: Color(0xFF4A90D9)),
            const SizedBox(width: 8),
            const Text('AI 诊断报告', style: TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        content: FutureBuilder<Map<String, dynamic>>(
          future: _api.getDiagnose(widget.code, market: widget.market, period: _period, days: _days),
          builder: (ctx, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const SizedBox(
                height: 200,
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 16),
                      Text('正在综合分析技术指标+K线形态+消息面...', style: TextStyle(fontSize: 13)),
                    ],
                  ),
                ),
              );
            }
            if (snapshot.hasError || !snapshot.hasData) {
              return SizedBox(
                height: 150,
                child: Center(
                  child: Text('分析失败: ${snapshot.error ?? "未知错误"}', style: const TextStyle(color: Colors.red)),
                ),
              );
            }
            final data = snapshot.data!;
            final score = (data['score'] as num?)?.toInt() ?? 50;
            final summary = data['summary'] as String? ?? '中性';
            final aiAnalysis = data['ai_analysis'] as String? ?? '暂无分析结果';
            final signals = (data['signals'] as List?)?.cast<Map<String, dynamic>>() ?? [];
            final patterns = (data['patterns'] as List?)?.cast<String>() ?? [];
            final indicators = data['indicators'] as Map<String, dynamic>? ?? {};

            final scoreColor = score >= 70 ? const Color(0xFFEF4444) :
                              score >= 50 ? const Color(0xFFF97316) :
                              const Color(0xFF22C55E);

            return SizedBox(
              height: 400,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 综合评分
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: scoreColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: scoreColor.withOpacity(0.3)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('$score', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: scoreColor)),
                          const SizedBox(width: 8),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(summary, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: scoreColor)),
                              Text('综合技术评分', style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5))),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),

                    // 技术指标快照
                    if (indicators.isNotEmpty) ...[
                      Text('📊 技术指标', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white.withOpacity(0.8))),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          _indicatorChip('RSI', '${(indicators['rsi'] as num?)?.toStringAsFixed(1) ?? '-'}'),
                          _indicatorChip('MACD DIF', '${(indicators['macd_dif'] as num?)?.toStringAsFixed(3) ?? '-'}'),
                          _indicatorChip('KDJ-K', '${(indicators['kdj_k'] as num?)?.toStringAsFixed(0) ?? '-'}'),
                          _indicatorChip('BOLL上', '${(indicators['boll_upper'] as num?)?.toStringAsFixed(2) ?? '-'}'),
                          _indicatorChip('BOLL下', '${(indicators['boll_lower'] as num?)?.toStringAsFixed(2) ?? '-'}'),
                        ],
                      ),
                      const SizedBox(height: 12),
                    ],

                    // 信号
                    if (signals.isNotEmpty) ...[
                      Text('⚡ 技术信号', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white.withOpacity(0.8))),
                      const SizedBox(height: 6),
                      ...signals.map((s) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(
                          children: [
                            Container(
                              width: 6, height: 6,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: _signalColor(s['type'] ?? ''),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(child: Text('[${s['source']}] ${s['text']}', style: const TextStyle(fontSize: 13))),
                          ],
                        ),
                      )),
                      const SizedBox(height: 12),
                    ],

                    // K线形态
                    if (patterns.isNotEmpty) ...[
                      Text('🕯️ K线形态', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white.withOpacity(0.8))),
                      const SizedBox(height: 6),
                      ...patterns.map((p) => Padding(
                        padding: const EdgeInsets.only(bottom: 4, left: 8),
                        child: Text('• $p', style: const TextStyle(fontSize: 13)),
                      )),
                      const SizedBox(height: 12),
                    ],

                    // AI分析
                    Text('🤖 AI 综合研判', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white.withOpacity(0.8))),
                    const SizedBox(height: 6),
                    ...aiAnalysis.split('\n').map((line) => Padding(
                      padding: const EdgeInsets.only(bottom: 2),
                      child: Text(line, style: const TextStyle(fontSize: 13)),
                    )),
                  ],
                ),
              ),
            );
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('关闭'),
          ),
        ],
      ),
    ).whenComplete(() {
      if (mounted) setState(() => _loadingDiagnose = false);
    });
  }

  Widget _indicatorChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text.rich(
        TextSpan(children: [
          TextSpan(text: '$label ', style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11)),
          TextSpan(text: value, style: const TextStyle(color: Color(0xFF4A90D9), fontSize: 12, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }

  Color _signalColor(String type) {
    switch (type) {
      case 'bullish': return const Color(0xFFEF4444);
      case 'danger': return const Color(0xFF22C55E);
      case 'warning': return const Color(0xFFF97316);
      default: return const Color(0xFF4A90D9);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Text(widget.name),
            const SizedBox(width: 6),
            if (widget.market.isNotEmpty)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: _marketColor.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  _marketLabel,
                  style: TextStyle(color: _marketColor, fontSize: 11, fontWeight: FontWeight.w600),
                ),
              ),
          ],
        ),
        actions: [],
      ),
      body: RefreshIndicator(
        onRefresh: _loadAll,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // ── 实时行情卡片 ──
            if (_trendData.isNotEmpty && _trendData['realtime'] != null)
              _buildRealtimeHeader()
            else if (_comment.isNotEmpty)
              _buildQuoteHeader(),
            const SizedBox(height: 16),

            // ── 分时/K线切换 ──
            _buildChartTabs(),
            const SizedBox(height: 8),
            Container(
              decoration: BoxDecoration(
                color: const Color(0xFF1A1A2E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: _showTrend
                  ? (_loadingTrend
                      ? const SizedBox(height: 270, child: Center(child: CircularProgressIndicator()))
                      : TrendChart(
                          trendData: _trendData,
                          currencySymbol: _currencySymbol,
                        ))
                  : (_loadingKline
                      ? const SizedBox(height: 300, child: Center(child: CircularProgressIndicator()))
                      : ProfessionalKlineChart(
                          data: _klineData,
                          currencySymbol: _currencySymbol,
                        )),
            ),
            const SizedBox(height: 20),

            // ── 技术信号速览 ──
            if (_indicators.isNotEmpty) ...[
              _buildSignalsCard(),
              const SizedBox(height: 20),
            ],

            // ── 机构数据 ──
            if (_comment.isNotEmpty) ...[
              _sectionTitle('机构数据'),
              const SizedBox(height: 8),
              _buildCommentCard(),
              const SizedBox(height: 20),
            ],

            // ── 一致预期 ──
            if (_profile.isNotEmpty && _profile['consensus'] != null) ...[
              _sectionTitle('券商一致预期'),
              const SizedBox(height: 8),
              _buildConsensusCard(),
              const SizedBox(height: 20),
            ],

            // ── 研报 ──
            if (_profile.isNotEmpty && (_profile['reports'] as List?)?.isNotEmpty == true) ...[
              _sectionTitle('最新研报'),
              const SizedBox(height: 8),
              ..._buildReports(),
              const SizedBox(height: 20),
            ],

            // ── 事件 ──
            _sectionTitle('相关事件'),
            const SizedBox(height: 8),
            if (_events.isEmpty)
              Container(
                padding: const EdgeInsets.all(32),
                alignment: Alignment.center,
                child: Text('暂无相关事件', style: TextStyle(color: Colors.white.withOpacity(0.3))),
              )
            else
              ..._events.map((e) => EventCard(event: e)),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _loadingDiagnose ? null : _showDiagnosis,
        icon: _loadingDiagnose
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.analytics),
        label: Text(_loadingDiagnose ? '分析中...' : 'AI 诊断'),
        backgroundColor: const Color(0xFF4A90D9),
      ),
    );
  }

  Color get _marketColor {
    switch (widget.market.toUpperCase()) {
      case 'HK': return const Color(0xFFFF6B35);
      case 'US': return const Color(0xFF4A90D9);
      default: return const Color(0xFFEF4444);
    }
  }

  String get _marketLabel {
    switch (widget.market.toUpperCase()) {
      case 'HK': return '港股';
      case 'US': return '美股';
      default: return 'A股';
    }
  }

  Widget _buildRealtimeHeader() {
    final rt = _trendData['realtime'] as Map<String, dynamic>? ?? {};
    final price = (rt['price'] as num?)?.toDouble() ?? 0;
    final changePct = (rt['changePct'] as num?)?.toDouble() ?? 0;
    final changeAmt = (rt['changeAmt'] as num?)?.toDouble() ?? 0;
    final high = (rt['high'] as num?)?.toDouble() ?? 0;
    final low = (rt['low'] as num?)?.toDouble() ?? 0;
    final open = (rt['open'] as num?)?.toDouble() ?? 0;
    final volume = (rt['volume'] as num?)?.toDouble() ?? 0;
    final prevClose = (rt['prevClose'] as num?)?.toDouble() ?? 0;
    final isUp = changePct >= 0;
    final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '$_currencySymbol${price.toStringAsFixed(2)}',
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: color),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${isUp ? "+" : ""}${changeAmt.toStringAsFixed(2)} (${isUp ? "+" : ""}${changePct.toStringAsFixed(2)}%)',
                    style: TextStyle(fontSize: 15, color: color, fontWeight: FontWeight.w600),
                  ),
                  if (_isTradingHours)
                    Row(
                      children: [
                        Container(
                          width: 6, height: 6,
                          decoration: const BoxDecoration(
                            shape: BoxShape.circle,
                            color: Color(0xFF22C55E),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Text('实时', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11)),
                      ],
                    ),
                ],
              ),
              const Spacer(),
              Text(widget.code, style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 13)),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _miniMetric('开盘', '$_currencySymbol${open.toStringAsFixed(2)}'),
              _miniMetric('最高', '$_currencySymbol${high.toStringAsFixed(2)}', color: const Color(0xFFEF4444)),
              _miniMetric('最低', '$_currencySymbol${low.toStringAsFixed(2)}', color: const Color(0xFF22C55E)),
              _miniMetric('昨收', '$_currencySymbol${prevClose.toStringAsFixed(2)}'),
              _miniMetric('成交量', _formatVol(volume)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _miniMetric(String label, String value, {Color color = const Color(0xFF4A90D9)}) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
        const SizedBox(height: 2),
        Text(label, style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.4))),
      ],
    );
  }

  String _formatVol(double vol) {
    if (vol >= 1e8) return '${(vol / 1e8).toStringAsFixed(1)}亿';
    if (vol >= 1e4) return '${(vol / 1e4).toStringAsFixed(0)}万';
    return vol.toStringAsFixed(0);
  }

  Widget _buildChartTabs() {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.04),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          _chartTab('分时', _showTrend, () {
            setState(() => _showTrend = true);
          }),
          _chartTab('K线', !_showTrend, () {
            setState(() => _showTrend = false);
          }),
          if (!_showTrend) ...[
            const Spacer(),
            PopupMenuButton<String>(
              icon: Icon(Icons.more_horiz, color: Colors.white.withOpacity(0.5), size: 18),
              onSelected: (v) {
                final parts = v.split('_');
                _switchPeriod(parts[0], int.parse(parts[1]), parts[2]);
              },
              itemBuilder: (_) => [
                const PopupMenuItem(value: '1m_1_1分', child: Text('1分钟')),
                const PopupMenuItem(value: '5m_2_5分', child: Text('5分钟')),
                const PopupMenuItem(value: '15m_3_15分', child: Text('15分钟')),
                const PopupMenuItem(value: '30m_4_30分', child: Text('30分钟')),
                const PopupMenuItem(value: '60m_5_60分', child: Text('60分钟')),
                const PopupMenuDivider(),
                const PopupMenuItem(value: 'daily_60_日K', child: Text('日K · 60天')),
                const PopupMenuItem(value: 'daily_120_日K', child: Text('日K · 120天')),
                const PopupMenuItem(value: 'daily_250_日K', child: Text('日K · 一年')),
                const PopupMenuDivider(),
                const PopupMenuItem(value: 'weekly_365_周K', child: Text('周K · 一年')),
                const PopupMenuItem(value: 'weekly_730_周K', child: Text('周K · 两年')),
                const PopupMenuItem(value: 'monthly_1000_月K', child: Text('月K · 全部')),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _chartTab(String label, bool isActive, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFF4A90D9).withOpacity(0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
          border: isActive ? Border.all(color: const Color(0xFF4A90D9).withOpacity(0.4)) : null,
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isActive ? const Color(0xFF4A90D9) : Colors.white.withOpacity(0.5),
            fontSize: 14,
            fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildQuoteHeader() {
    final price = (_comment['price'] as num?)?.toDouble() ?? 0;
    final changePct = (_comment['changePct'] as num?)?.toDouble() ?? 0;
    final changeAmt = (_comment['changeAmt'] as num?)?.toDouble() ?? 0;
    final isUp = changePct >= 0;
    final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '$_currencySymbol${price.toStringAsFixed(2)}',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: color),
              ),
              const SizedBox(width: 12),
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  '${isUp ? "+" : ""}${changeAmt.toStringAsFixed(2)} (${isUp ? "+" : ""}${changePct.toStringAsFixed(2)}%)',
                  style: TextStyle(fontSize: 14, color: color, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            widget.code,
            style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildPeriodTabs() {
    final tabs = [
      {'label': '1分', 'period': '1m', 'days': 1},
      {'label': '5分', 'period': '5m', 'days': 2},
      {'label': '15分', 'period': '15m', 'days': 3},
      {'label': '日K', 'period': 'daily', 'days': 120},
      {'label': '周K', 'period': 'weekly', 'days': 365},
      {'label': '月K', 'period': 'monthly', 'days': 1000},
    ];

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: tabs.map((t) {
        final isActive = _period == t['period'];
        return GestureDetector(
          onTap: () => _switchPeriod(t['period'] as String, t['days'] as int, t['label'] as String),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: isActive ? const Color(0xFF4A90D9).withOpacity(0.2) : Colors.transparent,
              borderRadius: BorderRadius.circular(6),
              border: isActive ? Border.all(color: const Color(0xFF4A90D9).withOpacity(0.4)) : null,
            ),
            child: Text(
              t['label'] as String,
              style: TextStyle(
                color: isActive ? const Color(0xFF4A90D9) : Colors.white.withOpacity(0.5),
                fontSize: 13,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSignalsCard() {
    final signals = (_indicators['signals'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final patterns = (_indicators['patterns'] as List?)?.cast<String>() ?? [];
    final score = (_indicators['score'] as num?)?.toInt() ?? 50;
    final summary = _indicators['summary'] as String? ?? '中性';
    final latest = _indicators['latest'] as Map<String, dynamic>? ?? {};

    final scoreColor = score >= 70 ? const Color(0xFFEF4444) :
                      score >= 50 ? const Color(0xFFF97316) :
                      const Color(0xFF22C55E);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('📊 技术面', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: scoreColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$score分 $summary',
                  style: TextStyle(color: scoreColor, fontSize: 13, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // 指标数值
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              _indicatorChip('RSI', (latest['rsi'] as num?)?.toStringAsFixed(1) ?? '-'),
              _indicatorChip('KDJ-K', (latest['kdj_k'] as num?)?.toStringAsFixed(0) ?? '-'),
              _indicatorChip('DIF', (latest['macd_dif'] as num?)?.toStringAsFixed(3) ?? '-'),
              _indicatorChip('BOLL上', (latest['boll_upper'] as num?)?.toStringAsFixed(2) ?? '-'),
              _indicatorChip('BOLL下', (latest['boll_lower'] as num?)?.toStringAsFixed(2) ?? '-'),
            ],
          ),

          if (signals.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 8),
            ...signals.take(4).map((s) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  Container(
                    width: 6, height: 6,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _signalColor(s['type'] ?? ''),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${s['text'] ?? ''}',
                      style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.8)),
                    ),
                  ),
                ],
              ),
            )),
          ],

          if (patterns.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: patterns.take(3).map((p) => Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF4A90D9).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(p, style: const TextStyle(color: Color(0xFF4A90D9), fontSize: 11)),
              )).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _sectionTitle(String title) {
    return Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white));
  }

  Widget _buildCommentCard() {
    final score = (_comment['compositeScore'] as num?)?.toDouble() ?? 0;
    final participation = (_comment['institutionParticipation'] as num?)?.toDouble() ?? 0;
    final mainCost = (_comment['mainCost'] as num?)?.toDouble() ?? 0;
    final attention = (_comment['attentionIndex'] as num?)?.toDouble() ?? 0;
    final rank = (_comment['currentRank'] as num?)?.toInt() ?? 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _metric('综合评分', score.toStringAsFixed(1), color: score >= 70 ? const Color(0xFFEF4444) : const Color(0xFF22C55E)),
              _metric('机构参与度', '${(participation * 100).toStringAsFixed(1)}%'),
              _metric('排名', '#$rank'),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _metric('主力成本', '$_currencySymbol${mainCost.toStringAsFixed(2)}'),
              _metric('关注指数', attention.toStringAsFixed(1)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildConsensusCard() {
    final consensus = _profile['consensus'] as Map<String, dynamic>? ?? {};
    final ratingDist = consensus['ratingDistribution'] as Map<String, dynamic>? ?? {};
    final avgEPS = (consensus['avgEPS2026'] as num?)?.toDouble();
    final avgPE = (consensus['avgPE2026'] as num?)?.toDouble();
    final buyRatio = (consensus['buyRatio'] as num?)?.toInt() ?? 0;
    final targetPrice = (_profile['targetPrice'] as num?)?.toDouble();
    final reportCount = (consensus['reportCount'] as num?)?.toInt() ?? 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            children: ratingDist.entries.map((e) {
              final color = e.key == '买入' ? const Color(0xFFEF4444) :
                            e.key == '增持' ? const Color(0xFFF97316) :
                            e.key == '中性' ? const Color(0xFF6B7280) :
                            const Color(0xFF22C55E);
              return Chip(
                label: Text('${e.key} ${e.value}%', style: TextStyle(color: color, fontSize: 12)),
                backgroundColor: color.withOpacity(0.1),
                side: BorderSide.none,
                padding: EdgeInsets.zero,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              );
            }).toList(),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              if (avgEPS != null) _metric('2026 EPS', '$_currencySymbol${avgEPS.toStringAsFixed(2)}'),
              if (avgPE != null) _metric('2026 PE', '${avgPE.toStringAsFixed(1)}x'),
              if (targetPrice != null && targetPrice > 0)
                _metric('目标价', '$_currencySymbol${targetPrice.toStringAsFixed(0)}',
                    color: targetPrice > (_comment['price'] ?? 0) ? const Color(0xFFEF4444) : const Color(0xFF22C55E)),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '买入占比 $buyRatio% · $reportCount 家机构覆盖',
            style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12),
          ),
        ],
      ),
    );
  }

  List<Widget> _buildReports() {
    final reports = _profile['reports'] as List? ?? [];
    return reports.take(5).map<Widget>((r) {
      final report = r as Map<String, dynamic>;
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1A2E),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0xFFEF4444).withOpacity(0.15),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(report['rating'] ?? '', style: const TextStyle(color: Color(0xFFEF4444), fontSize: 11, fontWeight: FontWeight.w600)),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    report['title'] ?? '',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13),
                  ),
                  Text(
                    '${report['institution'] ?? ''} · ${report['date'] ?? ''}',
                    style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  Widget _metric(String label, String value, {Color color = const Color(0xFF4A90D9)}) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
        const SizedBox(height: 2),
        Text(label, style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5))),
      ],
    );
  }
}
