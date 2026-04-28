class Stock {
  final String code;
  final String name;
  final String market; // 'A' / 'HK' / 'US'
  final DateTime? addedAt;
  final bool alertEnabled;

  Stock({
    required this.code,
    required this.name,
    this.market = '',
    this.addedAt,
    this.alertEnabled = true,
  });

  /// 市场显示标签
  String get marketLabel {
    switch (market.toUpperCase()) {
      case 'HK': return '港股';
      case 'US': return '美股';
      case 'A':
      case 'SH':
      case 'SZ': return 'A股';
      default: return '';
    }
  }

  /// 货币符号
  String get currencySymbol {
    switch (market.toUpperCase()) {
      case 'HK': return 'HK\$';
      case 'US': return '\$';
      default: return '¥';
    }
  }

  factory Stock.fromJson(Map<String, dynamic> json) {
    return Stock(
      code: json['code'] as String? ?? '',
      name: json['name'] as String? ?? '',
      market: json['market'] as String? ?? '',
      addedAt: json['addedAt'] != null
          ? DateTime.tryParse(json['addedAt'] as String)
          : null,
      alertEnabled: json['alertEnabled'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'code': code,
      'name': name,
      'market': market,
      'addedAt': addedAt?.toIso8601String(),
      'alertEnabled': alertEnabled,
    };
  }
}
