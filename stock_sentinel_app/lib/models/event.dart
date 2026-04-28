class SentinelEvent {
  final String id;
  final String code;
  final String type;
  final String title;
  final String detail;
  final String aiAnalysis;
  final String severity;
  final DateTime? createdAt;

  SentinelEvent({
    required this.id,
    required this.code,
    required this.type,
    required this.title,
    this.detail = '',
    this.aiAnalysis = '',
    this.severity = 'info',
    this.createdAt,
  });

  factory SentinelEvent.fromJson(Map<String, dynamic> json) {
    return SentinelEvent(
      id: (json['id'] ?? '').toString(),
      code: json['code'] as String? ?? '',
      type: json['type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      aiAnalysis: json['aiAnalysis'] as String? ?? '',
      severity: json['severity'] as String? ?? 'info',
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'] as String)
          : null,
    );
  }

  String get severityEmoji {
    switch (severity) {
      case 'high':
        return '🔴';
      case 'medium':
        return '🟠';
      case 'info':
      default:
        return '🔵';
    }
  }
}
