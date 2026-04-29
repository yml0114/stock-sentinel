import 'dart:async';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';
import '../services/news_service.dart';

class NewsScreen extends StatefulWidget {
  const NewsScreen({super.key});

  @override
  State<NewsScreen> createState() => _NewsScreenState();
}

class _NewsScreenState extends State<NewsScreen> {
  final _newsService = NewsService();
  final _api = ApiService();
  bool _loading = false;
  String _filter = 'all';

  @override
  void initState() {
    super.initState();
    _newsService.addListener(_onNewsUpdate);
    if (!_newsService.isLoaded) {
      setState(() => _loading = true);
    }
    _newsService.init().then((_) {
      if (mounted) setState(() => _loading = false);
    });
  }

  void _onNewsUpdate() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _newsService.removeListener(_onNewsUpdate);
    super.dispose();
  }

  Future<void> _manualRefresh() async {
    setState(() => _loading = true);
    await _newsService.refresh();
    if (mounted) setState(() => _loading = false);
  }

  List<Map<String, dynamic>> get _filteredNews {
    final news = _newsService.news;
    if (_filter == 'all') return news;
    if (_filter == 'bloomberg') {
      return news.where((n) =>
          n['source'] == 'Bloomberg' || n['source'] == '财新').toList();
    }
    if (_filter == 'international') {
      return news.where((n) => n['sourceType'] == 'international').toList();
    }
    return news.where((n) => n['sourceType'] != 'international').toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('全球财经'),
        actions: [
          IconButton(
            icon: _loading
                ? const SizedBox(width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.refresh, size: 22),
            onPressed: _loading ? null : _manualRefresh,
          ),
        ],
      ),
      body: Column(
        children: [
          _buildFilterBar(),
          Expanded(
            child: _loading && _newsService.news.isEmpty
                ? const Center(child: CircularProgressIndicator(strokeWidth: 2))
                : RefreshIndicator(
                    onRefresh: _manualRefresh,
                    child: _filteredNews.isEmpty
                        ? Center(child: Text('暂无新闻',
                            style: TextStyle(color: Colors.white.withOpacity(0.3))))
                        : ListView.separated(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            itemCount: _filteredNews.length,
                            separatorBuilder: (_, __) => Divider(
                              height: 1,
                              color: Colors.white.withOpacity(0.04),
                            ),
                            itemBuilder: (ctx, i) => _buildNewsItem(_filteredNews[i]),
                          ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar() {
    final filters = [
      {'key': 'all', 'label': '全部'},
      {'key': 'bloomberg', 'label': '权威'},
      {'key': 'international', 'label': '国际'},
      {'key': 'domestic', 'label': '国内'},
    ];

    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(
        children: filters.map((f) {
          final isActive = _filter == f['key'];
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: GestureDetector(
              onTap: () => setState(() => _filter = f['key'] as String),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: isActive
                      ? const Color(0xFF4A90D9).withOpacity(0.15)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isActive
                        ? const Color(0xFF4A90D9).withOpacity(0.4)
                        : Colors.white.withOpacity(0.08),
                  ),
                ),
                child: Text(
                  f['label'] as String,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                    color: isActive
                        ? const Color(0xFF4A90D9)
                        : Colors.white.withOpacity(0.5),
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  /// 新闻卡片 — 中文阅读习惯排版
  Widget _buildNewsItem(Map<String, dynamic> item) {
    final source = item['source'] ?? '';
    final sourceType = item['sourceType'] ?? '';
    final title = item['title'] ?? '';
    final titleEn = item['title_en'] ?? item['titleEn'] ?? '';
    final content = item['content'] ?? '';
    final time = item['time'] ?? '';
    final url = item['url'] ?? '';

    final isInternational = sourceType == 'international';
    final isTranslated = titleEn.toString().isNotEmpty;
    final hasUrl = url.toString().isNotEmpty;

    return GestureDetector(
      onTap: hasUrl ? () => _showFullArticle(item) : null,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── 来源 + 时间 ──
            Row(
              children: [
                _sourceTag(source, isInternational),
                if (isTranslated) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withOpacity(0.12),
                      borderRadius: BorderRadius.circular(3),
                    ),
                    child: const Text('译',
                        style: TextStyle(color: Color(0xFF10B981), fontSize: 10)),
                  ),
                ],
                const Spacer(),
                Text(_formatTimeAgo(time),
                    style: TextStyle(color: Colors.white.withOpacity(0.25), fontSize: 11)),
              ],
            ),
            const SizedBox(height: 8),

            // ── 标题（中文，大字号，加粗）──
            Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.white,
                height: 1.45,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),

            // ── 英文原标题（小字灰色，仅翻译过的显示）──
            if (isTranslated) ...[
              const SizedBox(height: 4),
              Text(
                titleEn,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withOpacity(0.25),
                  height: 1.3,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],

            // ── 内容摘要 ──
            if (content.toString().isNotEmpty && content != title) ...[
              const SizedBox(height: 6),
              Text(
                content,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.white.withOpacity(0.45),
                  height: 1.5,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],

            // ── 底部操作 ──
            if (hasUrl) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  _bottomAction(Icons.article_rounded, '全文', const Color(0xFF4A90D9),
                      () => _showFullArticle(item)),
                  const SizedBox(width: 16),
                  _bottomAction(Icons.open_in_new_rounded, '原文',
                      Colors.white.withOpacity(0.35),
                      () => _openUrl(url.toString())),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _sourceTag(String source, bool isInternational) {
    Color color;
    if (source == 'Bloomberg') {
      color = const Color(0xFFFF8C00);
    } else if (source == '财新') {
      color = const Color(0xFFE63946);
    } else if (source == '华尔街见闻') {
      color = const Color(0xFF8B5CF6);
    } else if (isInternational) {
      color = const Color(0xFF4A90D9);
    } else {
      color = Colors.white.withOpacity(0.4);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(source,
          style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w500)),
    );
  }

  Widget _bottomAction(IconData icon, String label, Color color, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(color: color, fontSize: 12)),
        ],
      ),
    );
  }

  /// 相对时间显示
  String _formatTimeAgo(String time) {
    if (time.isEmpty) return '';
    try {
      DateTime? dt;
      // 尝试解析各种格式
      if (time.contains('T') || time.contains('Z')) {
        dt = DateTime.tryParse(time.replaceAll(' Z', 'Z').replaceAll(' GMT', 'Z'));
      }
      if (dt == null) {
        // "2026-04-29 13:20:00" 格式
        dt = DateTime.tryParse(time);
      }
      if (dt == null) return time.length > 16 ? time.substring(11, 16) : time;

      // 确保是本地时间
      final now = DateTime.now();
      final diff = now.difference(dt);

      if (diff.isNegative) return time.length > 16 ? time.substring(11, 16) : time;
      if (diff.inMinutes < 1) return '刚刚';
      if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
      if (diff.inHours < 24) return '${diff.inHours}小时前';
      if (diff.inDays < 7) return '${diff.inDays}天前';
      return '${dt.month}/${dt.day}';
    } catch (_) {
      return time.length > 16 ? time.substring(11, 16) : time;
    }
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('无法打开链接')),
      );
    }
  }

  void _showFullArticle(Map<String, dynamic> item) {
    final url = item['url'] ?? '';
    if (url.toString().isEmpty) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF141420),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => _ArticleSheet(
        url: url.toString(),
        initialTitle: item['title'] ?? '',
        initialContent: item['content'] ?? '',
        api: _api,
      ),
    );
  }
}


/// 全文弹窗 — 自动翻译，中文优先
class _ArticleSheet extends StatefulWidget {
  final String url;
  final String initialTitle;
  final String initialContent;
  final ApiService api;

  const _ArticleSheet({
    required this.url,
    required this.initialTitle,
    required this.initialContent,
    required this.api,
  });

  @override
  State<_ArticleSheet> createState() => _ArticleSheetState();
}

class _ArticleSheetState extends State<_ArticleSheet> {
  bool _loading = true;
  String _title = '';
  String _content = '';
  String _titleEn = '';
  String _contentEn = '';
  bool _isTranslated = false;
  String _error = '';
  bool _showOriginal = false;

  @override
  void initState() {
    super.initState();
    _title = widget.initialTitle;
    _content = widget.initialContent;
    _fetchArticle();
  }

  Future<void> _fetchArticle() async {
    setState(() { _loading = true; _error = ''; });
    try {
      // 自动翻译模式：translate=true
      final result = await widget.api.getArticle(widget.url, translate: true);
      if (!mounted) return;
      setState(() {
        _loading = false;
        final content = (result['content'] ?? '').toString();
        if (content.isNotEmpty) {
          _title = result['title'] ?? widget.initialTitle;
          _content = content;
          _titleEn = (result['title_en'] ?? '').toString();
          _contentEn = (result['content_en'] ?? '').toString();
          _isTranslated = result['isTranslated'] ?? false;
        } else {
          _error = result['error'] ?? '无法获取正文';
          // 用列表里的摘要作为兜底
          _content = widget.initialContent;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '网络请求失败';
        _content = widget.initialContent;
      });
    }
  }

  Future<void> _openInBrowser() async {
    final uri = Uri.parse(widget.url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.9,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (ctx, scrollCtrl) => Column(
        children: [
          // ── 顶部拖拽条 + 关闭 ──
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 8, 0),
            child: Row(
              children: [
                Container(width: 36, height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const Spacer(),
                if (_isTranslated)
                  GestureDetector(
                    onTap: () => setState(() => _showOriginal = !_showOriginal),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.06),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        _showOriginal ? '中文' : 'English',
                        style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                      ),
                    ),
                  ),
                IconButton(
                  icon: Icon(Icons.close, color: Colors.white.withOpacity(0.3), size: 20),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          // ── 正文区域 ──
          Expanded(
            child: _loading
                ? const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(strokeWidth: 2),
                        SizedBox(height: 12),
                        Text('正在抓取全文并翻译...',
                            style: TextStyle(color: Colors.white38, fontSize: 13)),
                      ],
                    ),
                  )
                : ListView(
                    controller: scrollCtrl,
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                    children: [
                      // 标题
                      Text(
                        _showOriginal && _titleEn.isNotEmpty ? _titleEn : _title,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                          height: 1.4,
                        ),
                      ),
                      const SizedBox(height: 12),

                      // 翻译标识
                      if (_isTranslated)
                        Container(
                          margin: const EdgeInsets.only(bottom: 16),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFF10B981).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text('🌐 已自动翻译为中文',
                              style: TextStyle(color: Color(0xFF10B981), fontSize: 12)),
                        ),

                      // 错误提示
                      if (_error.isNotEmpty)
                        Container(
                          margin: const EdgeInsets.only(bottom: 16),
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.orange.withOpacity(0.08),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.info_outline, size: 16,
                                  color: Colors.orange.withOpacity(0.7)),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(_error,
                                    style: TextStyle(
                                        color: Colors.orange.withOpacity(0.7), fontSize: 12)),
                              ),
                            ],
                          ),
                        ),

                      // 分割线
                      Divider(color: Colors.white.withOpacity(0.06)),
                      const SizedBox(height: 12),

                      // 正文
                      Text(
                        _showOriginal && _contentEn.isNotEmpty ? _contentEn : _content,
                        style: TextStyle(
                          fontSize: 15,
                          color: Colors.white.withOpacity(0.8),
                          height: 1.8,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                  ),
          ),

          // ── 底部操作栏 ──
          Container(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 20),
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(color: Colors.white.withOpacity(0.06)),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: _openInBrowser,
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4A90D9).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.open_in_browser, size: 16,
                              color: Color(0xFF4A90D9)),
                          const SizedBox(width: 6),
                          Text('浏览器打开原文',
                              style: TextStyle(
                                  color: const Color(0xFF4A90D9).withOpacity(0.8),
                                  fontSize: 13)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
