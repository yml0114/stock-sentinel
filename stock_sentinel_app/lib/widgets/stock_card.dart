import 'package:flutter/material.dart';
import '../models/quote.dart';
import '../models/stock.dart';
import '../screens/stock_detail_screen.dart';

class StockCard extends StatelessWidget {
  final Stock stock;
  final Quote? quote;

  const StockCard({super.key, required this.stock, this.quote});

  @override
  Widget build(BuildContext context) {
    final isUp = quote != null && quote!.changePct >= 0;
    final changeColor = isUp ? Colors.red : Colors.green;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => StockDetailScreen(
                code: stock.code,
                name: stock.name,
                market: stock.market,
              ),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              // 左侧：代码+名称+市场标签
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            stock.name,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (stock.market.isNotEmpty) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                            decoration: BoxDecoration(
                              color: _marketColor(stock.market).withOpacity(0.15),
                              borderRadius: BorderRadius.circular(3),
                            ),
                            child: Text(
                              _marketLabel(stock.market),
                              style: TextStyle(
                                color: _marketColor(stock.market),
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      stock.code,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey[500],
                      ),
                    ),
                  ],
                ),
              ),
              // 右侧：价格+涨跌幅
              if (quote != null) ...[
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '${quote!.currencySymbol}${quote!.price.toStringAsFixed(2)}',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: changeColor,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${isUp ? '+' : ''}${quote!.changePct.toStringAsFixed(2)}%',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: changeColor,
                      ),
                    ),
                  ],
                ),
              ] else ...[
                Text(
                  '--',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey[500],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color _marketColor(String market) {
    switch (market.toUpperCase()) {
      case 'HK': return const Color(0xFFFF6B35);
      case 'US': return const Color(0xFF4A90D9);
      default: return const Color(0xFFEF4444);
    }
  }

  String _marketLabel(String market) {
    switch (market.toUpperCase()) {
      case 'HK': return '港';
      case 'US': return '美';
      default: return '';
    }
  }
}
