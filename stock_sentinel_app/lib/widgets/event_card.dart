import 'package:flutter/material.dart';
import '../models/event.dart';

class EventCard extends StatefulWidget {
  final SentinelEvent event;
  const EventCard({super.key, required this.event});

  @override
  State<EventCard> createState() => _EventCardState();
}

class _EventCardState extends State<EventCard> {
  void _showDetail() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF1A1A2E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.4,
        maxChildSize: 0.95,
        expand: false,
        builder: (ctx, scrollCtrl) => Padding(
          padding: const EdgeInsets.all(20),
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

              // 严重程度 + 类型
              Row(
                children: [
                  _severityIcon(20),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: _severityColor.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      widget.event.severity == 'high' ? '重要'
                        : widget.event.severity == 'medium' ? '关注' : '信息',
                      style: TextStyle(color: _severityColor, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                  if (widget.event.code.isNotEmpty && widget.event.code != 'GLOBAL') ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: Colors.blueGrey[800],
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(widget.event.code, style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                    ),
                  ],
                  const Spacer(),
                  if (widget.event.createdAt != null)
                    Text(_formatTime(widget.event.createdAt),
                        style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12)),
                ],
              ),
              const SizedBox(height: 16),

              // 标题
              Text(
                widget.event.title,
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white, height: 1.4),
              ),

              // 详情
              if (widget.event.detail.isNotEmpty && widget.event.detail != widget.event.title) ...[
                const SizedBox(height: 16),
                Divider(color: Colors.white.withOpacity(0.1)),
                const SizedBox(height: 16),
                Text(
                  widget.event.detail,
                  style: TextStyle(fontSize: 15, color: Colors.white.withOpacity(0.8), height: 1.7),
                ),
              ],

              // AI分析
              if (widget.event.aiAnalysis.isNotEmpty &&
                  !widget.event.aiAnalysis.contains('AI分析未配置')) ...[
                const SizedBox(height: 20),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF4A90D9).withOpacity(0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF4A90D9).withOpacity(0.15)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: const [
                          Icon(Icons.auto_awesome, size: 16, color: Color(0xFF4A90D9)),
                          SizedBox(width: 6),
                          Text('AI 分析', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF4A90D9))),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        widget.event.aiAnalysis,
                        style: TextStyle(fontSize: 14, color: Colors.white.withOpacity(0.75), height: 1.6),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color get _severityColor {
    switch (widget.event.severity) {
      case 'high': return Colors.red;
      case 'medium': return Colors.orange;
      default: return Colors.blue;
    }
  }

  /// 用 Flutter Icon 替代 emoji，避免乱码方块
  Widget _severityIcon(double size) {
    switch (widget.event.severity) {
      case 'high':
        return Icon(Icons.error_rounded, size: size, color: Colors.red);
      case 'medium':
        return Icon(Icons.warning_amber_rounded, size: size, color: Colors.orange);
      default:
        return Icon(Icons.info_rounded, size: size, color: Colors.blue);
    }
  }

  String _formatTime(DateTime? time) {
    if (time == null) return '';
    final diff = DateTime.now().difference(time);
    if (diff.inSeconds < 60) return '${diff.inSeconds}秒前';
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
    if (diff.inHours < 24) return '${diff.inHours}小时前';
    if (diff.inDays < 30) return '${diff.inDays}天前';
    return '${(diff.inDays / 30).floor()}月前';
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: _showDetail,
        child: Container(
          decoration: BoxDecoration(
            border: Border(left: BorderSide(color: _severityColor, width: 3)),
          ),
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 标题行
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _severityIcon(16),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      widget.event.title,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Colors.white),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(Icons.chevron_right, size: 18, color: Colors.white.withOpacity(0.3)),
                ],
              ),
              const SizedBox(height: 8),
              // 底部
              Row(
                children: [
                  Icon(Icons.access_time, size: 14, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(_formatTime(widget.event.createdAt),
                      style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  if (widget.event.code.isNotEmpty && widget.event.code != 'GLOBAL') ...[
                    const SizedBox(width: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.blueGrey[800],
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(widget.event.code,
                          style: TextStyle(fontSize: 11, color: Colors.grey[400])),
                    ),
                  ],
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: _severityColor.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      widget.event.severity == 'high' ? '重要'
                        : widget.event.severity == 'medium' ? '关注' : '信息',
                      style: TextStyle(fontSize: 10, color: _severityColor, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
