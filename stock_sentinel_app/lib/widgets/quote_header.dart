import 'package:flutter/material.dart';
import '../models/quote.dart';

class QuoteHeader extends StatelessWidget {
  final Quote quote;

  const QuoteHeader({super.key, required this.quote});

  String _formatVolume(double vol) {
    if (vol >= 100000000) return '${(vol / 100000000).toStringAsFixed(2)}亿';
    if (vol >= 10000) return '${(vol / 10000).toStringAsFixed(2)}万';
    return vol.toStringAsFixed(0);
  }

  @override
  Widget build(BuildContext context) {
    final isUp = quote.changePct >= 0;
    final changeColor = isUp ? Colors.red : Colors.green;
    final sign = isUp ? '+' : '';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          // 当前价格
          Text(
            quote.price.toStringAsFixed(2),
            style: TextStyle(
              fontSize: 42,
              fontWeight: FontWeight.bold,
              color: changeColor,
            ),
          ),
          const SizedBox(height: 8),
          // 涨跌额 + 涨跌幅
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '$sign${quote.changeAmount.toStringAsFixed(2)}',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: changeColor,
                ),
              ),
              const SizedBox(width: 16),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: changeColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '$sign${quote.changePct.toStringAsFixed(2)}%',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: changeColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // 行情指标
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildMetric('成交量', _formatVolume(quote.volume)),
              _buildMetric('成交额', _formatVolume(quote.amount)),
              _buildMetric('换手率', '${quote.turnover.toStringAsFixed(2)}%'),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildMetric('最高', quote.high.toStringAsFixed(2)),
              _buildMetric('最低', quote.low.toStringAsFixed(2)),
              _buildMetric('代码', quote.code),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Column(
      children: [
        Text(
          label,
          style: TextStyle(fontSize: 12, color: Colors.grey[500]),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: Colors.white70,
          ),
        ),
      ],
    );
  }
}
