import 'dart:math';
import 'package:flutter/material.dart';

/// 专业K线图组件 v8
/// 核心：只用 onScale*（不能和 onPan* 共存！）
/// 单指 = 拖动十字光标，双指 = 缩放，+/− 按钮辅助
class ProfessionalKlineChart extends StatefulWidget {
  final List<Map<String, dynamic>> data;
  final String currencySymbol;

  const ProfessionalKlineChart({
    super.key,
    required this.data,
    this.currencySymbol = '¥',
  });

  @override
  State<ProfessionalKlineChart> createState() => _ProfessionalKlineChartState();
}

class _ProfessionalKlineChartState extends State<ProfessionalKlineChart> {
  int? _crosshairIndex;
  double _scale = 1.0;
  double _baseScale = 1.0;
  bool _active = false;

  @override
  Widget build(BuildContext context) {
    if (widget.data.isEmpty) {
      return SizedBox(
        height: 300,
        child: Center(
          child: Text('暂无K线数据', style: TextStyle(color: Colors.white.withOpacity(0.4))),
        ),
      );
    }

    return Column(
      children: [
        _buildCrosshairInfo(),
        SizedBox(
          height: 280,
          child: GestureDetector(
            // ✅ 只用 onScale*，单指/双指都走这条路
            onScaleStart: (details) {
              _baseScale = _scale;
              _active = true;
            },
            onScaleUpdate: (details) {
              if (details.pointerCount == 1) {
                // 单指 → 拖动十字光标
                _updateCrosshair(details.localFocalPoint);
              } else if (details.pointerCount >= 2) {
                // 双指 → 缩放
                _scale = (_baseScale * details.scale).clamp(0.5, 5.0);
              }
              setState(() {});
            },
            onScaleEnd: (_) {
              _active = false;
              Future.delayed(const Duration(milliseconds: 800), () {
                if (!_active && mounted) {
                  setState(() {
                    _crosshairIndex = null;
                  });
                }
              });
            },
            behavior: HitTestBehavior.opaque,
            child: ClipRect(
              child: CustomPaint(
                size: const Size(double.infinity, 280),
                painter: _KlinePainter(
                  data: widget.data,
                  currencySymbol: widget.currencySymbol,
                  crosshairIndex: _crosshairIndex,
                  scale: _scale,
                ),
              ),
            ),
          ),
        ),
        // 缩放控制栏
        Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _scaleBtn(Icons.remove, () => setState(() => _scale = (_scale * 0.75).clamp(0.5, 5.0))),
              const SizedBox(width: 6),
              Text('${(_scale * 100).round()}%', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11)),
              const SizedBox(width: 6),
              _scaleBtn(Icons.add, () => setState(() => _scale = (_scale * 1.33).clamp(0.5, 5.0))),
              if (_scale != 1.0) ...[
                const SizedBox(width: 10),
                GestureDetector(
                  onTap: () => setState(() => _scale = 1.0),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.06),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text('重置', style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 11)),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _scaleBtn(IconData icon, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 32, height: 28,
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.06),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Icon(icon, color: Colors.white.withOpacity(0.5), size: 16),
      ),
    );
  }

  void _updateCrosshair(Offset localPos) {
    final count = widget.data.length;
    if (count == 0) return;

    const leftPad = 40.0;
    const rightPad = 50.0;
    final w = context.size?.width ?? 400;
    final chartWidth = w - leftPad - rightPad;
    if (localPos.dx < leftPad || localPos.dx > leftPad + chartWidth) return;

    // 可见范围
    final visibleCount = (count / _scale).round().clamp(6, count);
    final startIdx = (count - visibleCount).clamp(0, count);
    
    final idx = startIdx + ((localPos.dx - leftPad) / chartWidth * (visibleCount - 1)).round().clamp(0, visibleCount - 1);
    if (idx >= 0 && idx < count) {
      _crosshairIndex = idx;
    }
  }

  Widget _buildCrosshairInfo() {
    if (widget.data.isEmpty) return const SizedBox.shrink();
    
    final idx = (_crosshairIndex != null && _crosshairIndex! < widget.data.length)
        ? _crosshairIndex! : widget.data.length - 1;
    final d = widget.data[idx];
    
    final open = (d['open'] as num?)?.toDouble() ?? 0;
    final close = (d['close'] as num?)?.toDouble() ?? 0;
    final high = (d['high'] as num?)?.toDouble() ?? 0;
    final low = (d['low'] as num?)?.toDouble() ?? 0;
    final date = d['date'] ?? '';
    
    final isUp = close >= open;
    final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);
    final changePct = open > 0 ? (close - open) / open * 100 : 0;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      color: Colors.white.withOpacity(0.03),
      child: Row(
        children: [
          Text(date, style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(width: 8),
          _tag('开', '${widget.currencySymbol}${open.toStringAsFixed(2)}', color),
          _tag('收', '${widget.currencySymbol}${close.toStringAsFixed(2)}', color),
          _tag('高', '${widget.currencySymbol}${high.toStringAsFixed(2)}', const Color(0xFFEF4444)),
          _tag('低', '${widget.currencySymbol}${low.toStringAsFixed(2)}', const Color(0xFF22C55E)),
          _tag('幅', '${isUp ? "+" : ""}${changePct.toStringAsFixed(2)}%', color),
        ],
      ),
    );
  }

  Widget _tag(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: Text.rich(
        TextSpan(children: [
          TextSpan(text: '$label:', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 10)),
          TextSpan(text: value, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }
}


class _KlinePainter extends CustomPainter {
  final List<Map<String, dynamic>> data;
  final String currencySymbol;
  final int? crosshairIndex;
  final double scale;

  _KlinePainter({
    required this.data,
    this.currencySymbol = '¥',
    this.crosshairIndex,
    this.scale = 1.0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    const leftPad = 40.0;
    const rightPad = 50.0;
    const topPad = 8.0;
    const bottomPad = 24.0;
    final chartWidth = size.width - leftPad - rightPad;
    final chartHeight = size.height - topPad - bottomPad;

    // 根据缩放比例决定显示多少根K线
    final visibleCount = (data.length / scale).round().clamp(6, data.length);
    final startIdx = (data.length - visibleCount).clamp(0, data.length);
    final visible = data.sublist(startIdx);

    // 计算价格范围
    double minP = double.infinity, maxP = -double.infinity;
    for (final d in visible) {
      final low = (d['low'] as num?)?.toDouble() ?? 0;
      final high = (d['high'] as num?)?.toDouble() ?? 0;
      if (low < minP) minP = low;
      if (high > maxP) maxP = high;
    }

    // 含MA线
    if (visible.length >= 5) {
      for (int i = 4; i < visible.length; i++) {
        double sum = 0;
        for (int j = i - 4; j <= i; j++) {
          sum += (visible[j]['close'] as num?)?.toDouble() ?? 0;
        }
        final ma = sum / 5;
        if (ma < minP) minP = ma;
        if (ma > maxP) maxP = ma;
      }
    }

    final range = maxP - minP;
    final padding = range * 0.1;
    minP -= padding;
    maxP += padding;
    if (maxP <= minP) maxP = minP + 1;

    double priceToY(double price) {
      return topPad + chartHeight * (1 - (price - minP) / (maxP - minP));
    }

    // K线宽度和间距
    final candleWidth = (chartWidth / visible.length * 0.6).clamp(2.0, 16.0);
    final gap = chartWidth / visible.length;

    // 网格
    _drawGrid(canvas, size, leftPad, topPad, chartWidth, chartHeight, minP, maxP, bottomPad, visible, gap);

    // 画K线
    for (int i = 0; i < visible.length; i++) {
      final d = visible[i];
      final open = (d['open'] as num?)?.toDouble() ?? 0;
      final close = (d['close'] as num?)?.toDouble() ?? 0;
      final high = (d['high'] as num?)?.toDouble() ?? 0;
      final low = (d['low'] as num?)?.toDouble() ?? 0;

      final x = leftPad + gap * i + gap / 2;
      final isUp = close >= open;
      final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);

      // 影线
      final shadowPaint = Paint()..color = color..strokeWidth = 1;
      canvas.drawLine(
        Offset(x, priceToY(high)),
        Offset(x, priceToY(low)),
        shadowPaint,
      );

      // 实体
      final bodyTop = priceToY(max(open, close));
      final bodyBottom = priceToY(min(open, close));
      final bodyHeight = (bodyBottom - bodyTop).clamp(1.0, double.infinity);

      if (isUp) {
        // 空心（上涨）
        canvas.drawRect(
          Rect.fromLTWH(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight),
          Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 1,
        );
      } else {
        // 实心（下跌）
        canvas.drawRect(
          Rect.fromLTWH(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight),
          Paint()..color = color..style = PaintingStyle.fill,
        );
      }
    }

    // MA5线
    if (visible.length >= 5) {
      final maPath = Path();
      bool started = false;
      for (int i = 4; i < visible.length; i++) {
        double sum = 0;
        for (int j = i - 4; j <= i; j++) {
          sum += (visible[j]['close'] as num?)?.toDouble() ?? 0;
        }
        final ma = sum / 5;
        final x = leftPad + gap * i + gap / 2;
        final y = priceToY(ma);
        if (!started) { maPath.moveTo(x, y); started = true; } else { maPath.lineTo(x, y); }
      }
      canvas.drawPath(maPath, Paint()
        ..color = const Color(0xFFFFD700).withOpacity(0.7)
        ..strokeWidth = 1.0
        ..style = PaintingStyle.stroke);
    }

    // Y轴价格标签
    _drawPriceLabels(canvas, size, leftPad, topPad, chartHeight, minP, maxP);

    // 十字光标
    if (crosshairIndex != null) {
      final visIdx = crosshairIndex! - startIdx;
      if (visIdx >= 0 && visIdx < visible.length) {
        _drawCrosshair(canvas, size, chartHeight, topPad, leftPad, rightPad, priceToY, gap, visIdx);
      }
    }
  }

  void _drawGrid(Canvas canvas, Size size, double leftPad, double topPad,
      double chartWidth, double chartHeight, double minP, double maxP, double bottomPad,
      List<Map<String, dynamic>> visible, double gap) {
    final gridPaint = Paint()..color = Colors.white.withOpacity(0.04)..strokeWidth = 0.5;
    for (int i = 0; i <= 4; i++) {
      final y = topPad + chartHeight * i / 4;
      canvas.drawLine(Offset(leftPad, y), Offset(size.width - 50, y), gridPaint);
    }
  }

  void _drawPriceLabels(Canvas canvas, Size size, double leftPad, double topPad,
      double chartHeight, double minP, double maxP) {
    for (int i = 0; i <= 4; i++) {
      final price = maxP - (maxP - minP) * i / 4;
      final y = topPad + chartHeight * i / 4;
      final tp = TextPainter(
        text: TextSpan(text: price.toStringAsFixed(2), style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(2, y - tp.height / 2));
    }
  }

  void _drawCrosshair(Canvas canvas, Size size, double chartHeight, double topPad,
      double leftPad, double rightPad, double Function(double) priceToY,
      double gap, int visIdx) {
    if (visIdx < 0 || visIdx >= data.length) return;

    final d = data[visIdx]; // 用全局 data
    final cx = leftPad + gap * visIdx + gap / 2;
    final close = (d['close'] as num?)?.toDouble() ?? 0;
    final cy = priceToY(close);

    // 十字线
    final crossPaint = Paint()..color = Colors.white.withOpacity(0.3)..strokeWidth = 0.5;
    canvas.drawLine(Offset(leftPad, cy), Offset(size.width - rightPad, cy), crossPaint);
    canvas.drawLine(Offset(cx, topPad), Offset(cx, topPad + chartHeight), crossPaint);

    // 价格标签
    final priceRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(size.width - 28, cy), width: 56, height: 18),
      const Radius.circular(4),
    );
    canvas.drawRRect(priceRect, Paint()..color = const Color(0xFF4A90D9));
    final tp = TextPainter(
      text: TextSpan(text: close.toStringAsFixed(2), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(size.width - 28 - tp.width / 2, cy - tp.height / 2));

    // 日期标签
    final date = d['date'] ?? '';
    final shortDate = date.length > 5 ? date.substring(date.length - 5) : date;
    final dateRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(cx, topPad + chartHeight + 14), width: 50, height: 16),
      const Radius.circular(3),
    );
    canvas.drawRRect(dateRect, Paint()..color = const Color(0xFF4A90D9));
    final dateTp = TextPainter(
      text: TextSpan(text: shortDate, style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    dateTp.paint(canvas, Offset(cx - dateTp.width / 2, topPad + chartHeight + 14 - dateTp.height / 2));

    // 光标点
    canvas.drawCircle(Offset(cx, cy), 4, Paint()..color = const Color(0xFF4A90D9));
    canvas.drawCircle(Offset(cx, cy), 2, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(covariant _KlinePainter oldDelegate) {
    return oldDelegate.data != data || oldDelegate.crosshairIndex != crosshairIndex ||
        oldDelegate.scale != scale;
  }
}
