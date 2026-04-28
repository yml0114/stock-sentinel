import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';

class NewsScreen extends StatefulWidget {
  const NewsScreen({super.key});

  @override
  State<NewsScreen> createState() => _NewsScreenState();
}

class _NewsScreenState extends State<NewsScreen> {
  final _api = ApiService();
  List<Map<String, dynamic>> _news = [];
  bool _loading = true;
  String _filter = 'all';

  @override
  void initState() {
    super.initState();
    _loadNews();
  }

  Future<void> _loadNews() async {
    setState(() => _loading = true);
    try {
      final data = await _api.getNewsRaw(limit: 200);
      if (mounted) setState(() {
        _news = data;
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> get _filteredNews {
    if (_filter == 'all') return _news;
    if (_filter == 'bloomberg') {
      return _news.where((n) => n['source'] == 'Bloomberg' || n['source'] == '财新').toList();
    }
    if (_filter == 'international') {
      return _news.where((n) => n['sourceType'] == 'international').toList();
    }
    return _news.where((n) => n['sourceType'] != 'international').toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('全球新闻'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadNews,
          ),
        ],
      ),
      body: Column(
        children: [
          _buildFilterBar(),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
                    onRefresh: _loadNews,
                    child: _filteredNews.isEmpty
                        ? Center(
                            child: Text('暂无新闻', style: TextStyle(color: Colors.white.withOpacity(0.4))),
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.only(top: 4, bottom: 20),
                            itemCount: _filteredNews.length,
                            itemBuilder: (ctx, i) => _buildNewsCard(_filteredNews[i]),
                          ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar() {
    final filters = [
      {'key': 'all', 'label': '全部', 'icon': Icons.language},
      {'key': 'bloomberg', 'label': '权威', 'icon': Icons.business},
      {'key': 'international', 'label': '国际', 'icon': Icons.public},
      {'key': 'domestic', 'label': '国内', 'icon': Icons.home},
    ];

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: filters.map((f) {
          final isActive = _filter == f['key'];
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: GestureDetector(
                onTap: () => setState(() => _filter = f['key'] as String),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: isActive
                        ? const Color(0xFF4A90D9).withOpacity(0.2)
                        : Colors.white.withOpacity(0.04),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isActive
                          ? const Color(0xFF4A90D9).withOpacity(0.5)
                          : Colors.white.withOpacity(0.06),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(f['icon'] as IconData, size: 14,
                          color: isActive ? const Color(0xFF4A90D9) : Colors.white.withOpacity(0.5)),
                      const SizedBox(width: 4),
                      Text(
                        f['label'] as String,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                          color: isActive ? const Color(0xFF4A90D9) : Colors.white.withOpacity(0.6),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildNewsCard(Map<String, dynamic> item) {
    final source = item['source'] ?? '';
    final sourceType = item['sourceType'] ?? '';
    final title = item['title'] ?? '';
    final titleEn = item['title_en'] ?? item['titleEn'] ?? '';
    final content = item['content'] ?? '';
    final time = item['time'] ?? '';
    final url = item['url'] ?? '';

    final isInternational = sourceType == 'international';
    final isTranslated = titleEn.isNotEmpty;
    final hasUrl = url.toString().isNotEmpty;

    Color sourceColor;
    if (source == 'Bloomberg') {
      sourceColor = const Color(0xFFFF8C00);
    } else if (source == '财新') {
      sourceColor = const Color(0xFFE63946);
    } else if (isInternational) {
      sourceColor = const Color(0xFF4A90D9);
    } else {
      sourceColor = const Color(0xFF6B7280);
    }

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 源标签 + 时间
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: sourceColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    source,
                    style: TextStyle(color: sourceColor, fontSize: 11, fontWeight: FontWeight.w600),
                  ),
                ),
                if (isTranslated) ...[
                  const SizedBox(width: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(
                      color: Colors.green.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(3),
                    ),
                    child: const Text('已翻译', style: TextStyle(color: Colors.green, fontSize: 9)),
                  ),
                ],
                const Spacer(),
                if (time.isNotEmpty)
                  Text(_formatTime(time), style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 11)),
              ],
            ),
            const SizedBox(height: 8),

            // 标题（中文）
            Text(
              title,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: Colors.white,
                height: 1.4,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),

            // 英文原标题（翻译过的才显示）
            if (titleEn.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                titleEn,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withOpacity(0.35),
                  fontStyle: FontStyle.italic,
                  height: 1.3,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],

            // 内容摘要
            if (content.isNotEmpty && content != title) ...[
              const SizedBox(height: 6),
              Text(
                content,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.white.withOpacity(0.5),
                  height: 1.4,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],

            // 操作按钮行：全文 + 原文
            const SizedBox(height: 10),
            Row(
              children: [
                // 全文按钮（抓取+翻译中文全文，APP内展示）
                if (hasUrl)
                  _actionButton(
                    icon: Icons.article_outlined,
                    label: '全文',
                    color: const Color(0xFF4A90D9),
                    onTap: () => _showFullArticle(item),
                  ),
                if (hasUrl) const SizedBox(width: 8),
                // 原文按钮（浏览器打开）
                if (hasUrl)
                  _actionButton(
                    icon: Icons.open_in_browser,
                    label: '原文',
                    color: Colors.white.withOpacity(0.4),
                    onTap: () => _openOriginalUrl(url.toString()),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }

  /// 用浏览器打开原文链接
  Future<void> _openOriginalUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('无法打开: $url'), backgroundColor: Colors.red.withOpacity(0.8)),
        );
      }
    }
  }

  /// 展示全文（抓取+翻译中文）— APP内弹出
  void _showFullArticle(Map<String, dynamic> item) {
    final url = item['url'] ?? '';
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF1E1E2E),
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

  String _formatTime(String time) {
    if (time.isEmpty) return '';
    if (time.length > 16) return time.substring(11, 16);
    return time;
  }
}


/// 全文展示弹窗 — 抓取+翻译+原文按钮
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
  bool _loading = false;
  bool _loaded = false;
  String _titleZh = '';
  String _contentZh = '';
  String _titleEn = '';
  String _contentEn = '';
  bool _isTranslated = false;
  String _error = '';
  bool _showOriginal = false; // 是否显示英文原文

  @override
  void initState() {
    super.initState();
    // 自动开始抓取全文
    _fetchArticle();
  }

  Future<void> _fetchArticle() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final result = await widget.api.getArticle(widget.url);
      if (mounted) setState(() {
        _loading = false;
        _loaded = true;
        
        final success = result['success'] ?? false;
        if (success || (result['content'] ?? '').toString().isNotEmpty) {
          // 中文内容
          _titleZh = result['title'] ?? widget.initialTitle;
          _contentZh = result['content'] ?? '';
          
          // 英文原文
          _titleEn = result['title_en'] ?? '';
          _contentEn = result['content_en'] ?? '';
          _isTranslated = result['isTranslated'] ?? false;
          
          // 如果没有抓到正文，用列表的摘要
          if (_contentZh.isEmpty) {
            _contentZh = widget.initialContent;
          }
        } else {
          _error = result['error'] ?? '无法获取正文';
          // 降级：用列表摘要
          _titleZh = widget.initialTitle;
          _contentZh = widget.initialContent;
        }
      });
    } catch (e) {
      if (mounted) setState(() {
        _loading = false;
        _loaded = true;
        _error = '网络请求失败: $e';
        _titleZh = widget.initialTitle;
        _contentZh = widget.initialContent;
      });
    }
  }

  Future<void> _openOriginalUrl() async {
    final uri = Uri.parse(widget.url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('无法打开: ${widget.url}'), backgroundColor: Colors.red.withOpacity(0.8)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (ctx, scrollCtrl) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
        child: ListView(
          controller: scrollCtrl,
          children: [
            // 拖拽指示条
            Center(
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // 标题区域
            if (_loading) ...[
              Container(
                padding: const EdgeInsets.all(20),
                child: const Column(
                  children: [
                    CircularProgressIndicator(strokeWidth: 2),
                    SizedBox(height: 12),
                    Text('正在抓取全文并翻译...', style: TextStyle(color: Colors.white54, fontSize: 13)),
                  ],
                ),
              ),
            ] else ...[
              // 标题
              Text(
                _showOriginal && _titleEn.isNotEmpty ? _titleEn : _titleZh,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  height: 1.4,
                ),
              ),

              // 翻译标记
              if (_isTranslated) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.green.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text('AI翻译 · Google Translate', style: TextStyle(color: Colors.green, fontSize: 11)),
                ),
              ],

              // 错误提示
              if (_error.isNotEmpty) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(_error, style: TextStyle(color: Colors.orange.withOpacity(0.8), fontSize: 12)),
                ),
              ],

              const SizedBox(height: 16),
              Divider(color: Colors.white.withOpacity(0.1)),
              const SizedBox(height: 16),

              // 正文（中文或英文，取决于 _showOriginal）
              Text(
                _showOriginal && _contentEn.isNotEmpty ? _contentEn : _contentZh,
                style: TextStyle(
                  fontSize: 15,
                  color: Colors.white.withOpacity(0.85),
                  height: 1.7,
                ),
              ),
            ],

            // 底部操作按钮
            const SizedBox(height: 24),
            Divider(color: Colors.white.withOpacity(0.08)),
            const SizedBox(height: 12),

            Row(
              children: [
                // 切换中文/英文按钮（如果有翻译）
                if (_isTranslated && _contentEn.isNotEmpty)
                  Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _showOriginal = !_showOriginal),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.06),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: Colors.white.withOpacity(0.1)),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.translate, size: 16, color: Colors.white.withOpacity(0.5)),
                            const SizedBox(width: 6),
                            Text(
                              _showOriginal ? '中文' : 'English',
                              style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                if (_isTranslated && _contentEn.isNotEmpty) const SizedBox(width: 12),

                // 浏览器打开原文按钮
                Expanded(
                  child: GestureDetector(
                    onTap: _openOriginalUrl,
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF4A90D9).withOpacity(0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF4A90D9).withOpacity(0.3)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.open_in_browser, size: 16, color: Color(0xFF4A90D9)),
                          const SizedBox(width: 6),
                          Text('浏览器打开', style: TextStyle(color: const Color(0xFF4A90D9).withOpacity(0.8), fontSize: 13)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
