class Quote {
  final String code;
  final String name;
  final String market; // 'A' / 'HK' / 'US'
  final double price;
  final double changePct;
  final double changeAmt;
  final double volume;
  final double amount;
  final double high;
  final double low;
  final double open;
  final double prevClose;
  final double turnover;
  final double amplitude;
  final double peRatio;
  final double marketCap;
  final DateTime? timestamp;

  Quote({
    required this.code,
    required this.name,
    this.market = '',
    required this.price,
    required this.changePct,
    this.changeAmt = 0,
    this.volume = 0,
    this.amount = 0,
    this.high = 0,
    this.low = 0,
    this.open = 0,
    this.prevClose = 0,
    this.turnover = 0,
    this.amplitude = 0,
    this.peRatio = 0,
    this.marketCap = 0,
    this.timestamp,
  });

  /// 币种符号
  String get currencySymbol {
    switch (market.toUpperCase()) {
      case 'HK': return 'HK\$';
      case 'US': return '\$';
      default: return '¥';
    }
  }

  factory Quote.fromJson(Map<String, dynamic> json) {
    return Quote(
      code: json['code'] as String? ?? '',
      name: json['name'] as String? ?? '',
      market: json['market'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      changePct: (json['changePct'] as num?)?.toDouble() ?? 0,
      changeAmt: (json['changeAmt'] as num?)?.toDouble() ?? 0,
      volume: (json['volume'] as num?)?.toDouble() ?? 0,
      amount: (json['amount'] as num?)?.toDouble() ?? 0,
      high: (json['high'] as num?)?.toDouble() ?? 0,
      low: (json['low'] as num?)?.toDouble() ?? 0,
      open: (json['open'] as num?)?.toDouble() ?? 0,
      prevClose: (json['prevClose'] as num?)?.toDouble() ?? 0,
      turnover: (json['turnover'] as num?)?.toDouble() ?? 0,
      amplitude: (json['amplitude'] as num?)?.toDouble() ?? 0,
      peRatio: (json['peRatio'] as num?)?.toDouble() ?? 0,
      marketCap: (json['marketCap'] as num?)?.toDouble() ?? 0,
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'] as String)
          : null,
    );
  }

  /// 涨跌额
  double get changeAmount => changeAmt != 0 ? changeAmt : price * changePct / 100;
}
