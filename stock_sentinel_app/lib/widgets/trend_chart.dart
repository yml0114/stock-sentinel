import 'dart:math';
import 'package:flutter/material.dart';

/// 分时走势线组件 — 平滑价格线 + 均价线 + 昨收参考线 + 渐变填充 + 十字光标
class TrendChart extends StatefulWidget {
  final Map<String, dynamic> trendData;
  final String currencySymbol;

  const TrendChart({
    super.key,
    required this.trendData,
    this.currencySymbol = '¥',
  });

  @override
  State<TrendChart> createState() => _TrendChartState();
}

class _TrendChartState extends State<TrendChart> {
  int? _crosshairIndex;
  Offset? _crosshairPos;

  List<Map<String, dynamic>> get _points {
    final raw = widget.trendData['trend'] as List? ?? [];
    return raw.cast<Map<String, dynamic>>();
  }

  double get _prevClose {
    final rt = widget.trendData['realtime'] as Map<String, dynamic>? ?? {};
    return (rt['prevClose'] as num?)?.toDouble() ?? 0;
  }

  @override
  Widget build(BuildContext context) {
    if (_points.isEmpty) {
      return SizedBox(
        height: 250,
        child: Center(
          child: Text('暂无走势数据', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 14)),
        ),
      );
    }

    return Column(
      children: [
        // 十字光标信息栏
        _buildCrosshairInfo(),
        // 分时图主体
        SizedBox(
          height: 250,
          child: GestureDetector(
            onLongPressStart: (details) {
              _updateCrosshair(details.localPosition);
              setState(() {});
            },
            onLongPressMoveUpdate: (details) {
              _updateCrosshair(details.localPosition);
              setState(() {});
            },
            onLongPressEnd: (_) {
              setState(() {
                _crosshairIndex = null;
                _crosshairPos = null;
              });
            },
            child: CustomPaint(
              size: const Size(double.infinity, 250),
              painter: _TrendPainter(
                points: _points,
                prevClose: _prevClose,
                currencySymbol: widget.currencySymbol,
                crosshairIndex: _crosshairIndex,
                crosshairPos: _crosshairPos,
              ),
            ),
          ),
        ),
      ],
    );
  }

  void _updateCrosshair(Offset localPos) {
    final w = MediaQuery.of(context).size.width;
    final count = _points.length;
    if (count == 0) return;

    const leftPad = 40.0;
    const rightPad = 50.0;
    final chartWidth = w - leftPad - rightPad;
    if (localPos.dx < leftPad || localPos.dx > leftPad + chartWidth) return;

    final idx = ((localPos.dx - leftPad) / chartWidth * (count - 1)).round().clamp(0, count - 1);
    setState(() {
      _crosshairIndex = idx;
      _crosshairPos = localPos;
    });
  }

  Widget _buildCrosshairInfo() {
    if (_crosshairIndex == null || _crosshairIndex! >= _points.length) {
      return const SizedBox.shrink();
    }

    final p = _points[_crosshairIndex!];
    final price = (p['price'] as num?)?.toDouble() ?? 0;
    final avg = (p['avg_price'] as num?)?.toDouble() ?? 0;
    final time = _shortenTime(p['time'] ?? '');
    final change = price - _prevClose;
    final changePct = _prevClose > 0 ? change / _prevClose * 100 : 0;
    final isUp = change >= 0;
    final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      color: Colors.white.withOpacity(0.03),
      child: Row(
        children: [
          Text('$time', style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(width: 8),
          _tag('价', '${widget.currencySymbol}${price.toStringAsFixed(2)}', color),
          _tag('均', '${widget.currencySymbol}${avg.toStringAsFixed(2)}', const Color(0xFFFFD700)),
          _tag('涨跌', '${isUp ? "+" : ""}${changePct.toStringAsFixed(2)}%', color),
        ],
      ),
    );
  }

  Widget _tag(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Text.rich(
        TextSpan(children: [
          TextSpan(text: '$label:', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11)),
          TextSpan(text: value, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }

  /// "2026-04-29 09:35:00" → "09:35"
  String _shortenTime(String raw) {
    if (raw.length >= 16 && raw.contains(' ')) {
      return raw.split(' ').last.substring(0, 5);
    }
    if (raw.length >= 5) return raw.substring(0, 5);
    return raw;
  }
}


class _TrendPainter extends CustomPainter {
  final List<Map<String, dynamic>> points;
  final double prevClose;
  final String currencySymbol;
  final int? crosshairIndex;
  final Offset? crosshairPos;

  _TrendPainter({
    required this.points,
    required this.prevClose,
    this.currencySymbol = '¥',
    this.crosshairIndex,
    this.crosshairPos,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;

    const leftPad = 40.0;
    const rightPad = 50.0;
    const topPad = 8.0;
    const bottomPad = 24.0;
    final chartWidth = size.width - leftPad - rightPad;
    final chartHeight = size.height - topPad - bottomPad;

    // Extract prices and compute range
    final prices = points.map((p) => (p['price'] as num?)?.toDouble() ?? 0).toList();
    final avgs = points.map((p) => (p['avg_price'] as num?)?.toDouble() ?? 0).toList();

    double minP = prices.reduce(min);
    double maxP = prices.reduce(max);

    // Include avg prices in range
    for (final a in avgs) {
      if (a > 0) {
        if (a < minP) minP = a;
        if (a > maxP) maxP = a;
      }
    }

    // Include prevClose in range for reference
    if (prevClose > 0) {
      if (prevClose < minP) minP = prevClose;
      if (prevClose > maxP) maxP = prevClose;
    }

    final range = maxP - minP;
    final padding = range * 0.1;
    minP -= padding;
    maxP += padding;
    if (maxP <= minP) maxP = minP + 1;

    double priceToY(double price) {
      return topPad + chartHeight * (1 - (price - minP) / (maxP - minP));
    }

    double indexToX(int i) {
      return leftPad + chartWidth * i / (points.length - 1).clamp(1, points.length);
    }

    // Draw grid
    _drawGrid(canvas, size, leftPad, topPad, chartWidth, chartHeight, minP, maxP, bottomPad);

    // Draw prevClose reference line (white dashed)
    if (prevClose > 0) {
      final pcY = priceToY(prevClose);
      final dashPaint = Paint()
        ..color = Colors.white.withOpacity(0.35)
        ..strokeWidth = 0.8
        ..style = PaintingStyle.stroke;
      _drawDashedLine(canvas, Offset(leftPad, pcY), Offset(size.width - rightPad, pcY), dashPaint, dashWidth: 4, dashSpace: 3);

      // Label: 昨收
      final tp = TextPainter(
        text: TextSpan(
          text: '昨收',
          style: TextStyle(color: Colors.white.withOpacity(0.35), fontSize: 9),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(size.width - rightPad + 4, pcY - tp.height / 2));
    }

    // Build price path
    final pricePath = Path();
    for (int i = 0; i < points.length; i++) {
      final x = indexToX(i);
      final y = priceToY(prices[i]);
      if (i == 0) {
        pricePath.moveTo(x, y);
      } else {
        // Smooth curve using quadratic bezier
        final prevX = indexToX(i - 1);
        final prevY = priceToY(prices[i - 1]);
        final cpX = (prevX + x) / 2;
        pricePath.quadraticBezierTo(cpX, prevY, x, y);
      }
    }

    // Draw gradient fill under price line
    final fillPath = Path.from(pricePath);
    fillPath.lineTo(indexToX(points.length - 1), topPad + chartHeight);
    fillPath.lineTo(indexToX(0), topPad + chartHeight);
    fillPath.close();

    final gradientPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          const Color(0xFF00BCD4).withOpacity(0.25),
          const Color(0xFF00BCD4).withOpacity(0.02),
        ],
      ).createShader(Rect.fromLTWH(leftPad, topPad, chartWidth, chartHeight));
    canvas.drawPath(fillPath, gradientPaint);

    // Draw price line (teal/cyan)
    final linePaint = Paint()
      ..color = const Color(0xFF00BCD4)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    canvas.drawPath(pricePath, linePaint);

    // Draw average price line (yellow dashed)
    final avgPath = Path();
    bool avgStarted = false;
    for (int i = 0; i < points.length; i++) {
      if (avgs[i] <= 0) continue;
      final x = indexToX(i);
      final y = priceToY(avgs[i]);
      if (!avgStarted) {
        avgPath.moveTo(x, y);
        avgStarted = true;
      } else {
        avgPath.lineTo(x, y);
      }
    }
    final avgPaint = Paint()
      ..color = const Color(0xFFFFD700).withOpacity(0.8)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;
    canvas.drawPath(avgPath, avgPaint);

    // Draw current price dot
    final lastPrice = prices.last;
    final lastX = indexToX(points.length - 1);
    final lastY = priceToY(lastPrice);
    canvas.drawCircle(Offset(lastX, lastY), 3, Paint()..color = const Color(0xFF00BCD4));

    // Draw time labels (X-axis)
    _drawTimeLabels(canvas, size, topPad, chartHeight, leftPad, rightPad, bottomPad);

    // Draw price labels (Y-axis)
    _drawPriceLabels(canvas, size, leftPad, topPad, chartHeight, minP, maxP);

    // Draw crosshair
    if (crosshairIndex != null && crosshairPos != null) {
      _drawCrosshair(canvas, size, chartHeight, topPad, leftPad, rightPad, priceToY, indexToX);
    }
  }

  void _drawGrid(Canvas canvas, Size size, double leftPad, double topPad,
      double chartWidth, double chartHeight, double minP, double maxP, double bottomPad) {
    final gridPaint = Paint()
      ..color = Colors.white.withOpacity(0.04)
      ..strokeWidth = 0.5;

    // Horizontal grid lines
    for (int i = 0; i <= 4; i++) {
      final y = topPad + chartHeight * i / 4;
      canvas.drawLine(Offset(leftPad, y), Offset(size.width - 50, y), gridPaint);
    }

    // Vertical grid lines (at key times)
    final timeIndices = <int>[];
    for (int i = 0; i < points.length; i++) {
      final rawTime = points[i]['time'] ?? '';
      final t = _shortTime(rawTime);
      if (t == '09:30' || t == '10:00' || t == '10:30' || t == '11:00' ||
          t == '11:30' || t == '13:00' || t == '13:30' || t == '14:00' ||
          t == '14:30' || t == '15:00') {
        timeIndices.add(i);
      }
    }
    for (final i in timeIndices) {
      final x = leftPad + chartWidth * i / (points.length - 1).clamp(1, points.length);
      canvas.drawLine(Offset(x, topPad), Offset(x, topPad + chartHeight), gridPaint);
    }
  }

  void _drawTimeLabels(Canvas canvas, Size size, double topPad, double chartHeight,
      double leftPad, double rightPad, double bottomPad) {
    // Show key time labels
    final keyTimes = ['09:30', '10:00', '10:30', '11:00', '11:30', '13:00', '13:30', '14:00', '14:30', '15:00'];
    final chartWidth = size.width - leftPad - rightPad;

    for (int i = 0; i < points.length; i++) {
      final rawTime = points[i]['time'] ?? '';
      final t = _shortTime(rawTime);
      if (!keyTimes.contains(t)) continue;

      // Only label every other key time to avoid overcrowding
      final ki = keyTimes.indexOf(t);
      if (ki % 2 != 0 && ki != keyTimes.length - 1) continue;

      final x = leftPad + chartWidth * i / (points.length - 1).clamp(1, points.length);
      final tp = TextPainter(
        text: TextSpan(
          text: t.substring(0, 5),
          style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(x - tp.width / 2, topPad + chartHeight + 6));
    }
  }

  void _drawPriceLabels(Canvas canvas, Size size, double leftPad, double topPad,
      double chartHeight, double minP, double maxP) {
    for (int i = 0; i <= 4; i++) {
      final price = maxP - (maxP - minP) * i / 4;
      final y = topPad + chartHeight * i / 4;
      final tp = TextPainter(
        text: TextSpan(
          text: price.toStringAsFixed(2),
          style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(2, y - tp.height / 2));

      // Right side: show change percentage from prevClose
      if (prevClose > 0) {
        final changePct = (price - prevClose) / prevClose * 100;
        final pctColor = changePct >= 0 ? const Color(0xFFEF4444) : const Color(0xFF22C55E);
        final pctTp = TextPainter(
          text: TextSpan(
            text: '${changePct >= 0 ? '+' : ''}${changePct.toStringAsFixed(2)}%',
            style: TextStyle(color: pctColor.withOpacity(0.4), fontSize: 9),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        pctTp.paint(canvas, Offset(size.width - 48, y - pctTp.height / 2));
      }
    }
  }

  void _drawDashedLine(Canvas canvas, Offset start, Offset end, Paint paint, {double dashWidth = 4, double dashSpace = 3}) {
    final dx = end.dx - start.dx;
    final dy = end.dy - start.dy;
    final distance = sqrt(dx * dx + dy * dy);
    final count = (distance / (dashWidth + dashSpace)).floor();
    final unitDx = dx / distance;
    final unitDy = dy / distance;

    for (int i = 0; i < count; i++) {
      final startX = start.dx + unitDx * (dashWidth + dashSpace) * i;
      final startY = start.dy + unitDy * (dashWidth + dashSpace) * i;
      final endX = startX + unitDx * dashWidth;
      final endY = startY + unitDy * dashWidth;
      canvas.drawLine(Offset(startX, startY), Offset(endX, endY), paint);
    }
  }

  void _drawCrosshair(Canvas canvas, Size size, double chartHeight, double topPad,
      double leftPad, double rightPad, double Function(double) priceToY, double Function(int) indexToX) {
    final idx = crosshairIndex!;
    if (idx < 0 || idx >= points.length) return;

    final cx = indexToX(idx);
    final price = (points[idx]['price'] as num?)?.toDouble() ?? 0;
    final cy = priceToY(price);

    // Horizontal + vertical crosshair lines
    final crossPaint = Paint()
      ..color = Colors.white.withOpacity(0.3)
      ..strokeWidth = 0.5;
    canvas.drawLine(Offset(leftPad, cy), Offset(size.width - rightPad, cy), crossPaint);
    canvas.drawLine(Offset(cx, topPad), Offset(cx, topPad + chartHeight), crossPaint);

    // Price label on right
    final priceRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(size.width - 28, cy), width: 56, height: 18),
      const Radius.circular(4),
    );
    canvas.drawRRect(priceRect, Paint()..color = const Color(0xFF00BCD4));
    final tp = TextPainter(
      text: TextSpan(text: price.toStringAsFixed(2), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(size.width - 28 - tp.width / 2, cy - tp.height / 2));

    // Time label on bottom
    final time = _shortTime(points[idx]['time'] ?? '');
    final timeRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(cx, topPad + chartHeight + 14), width: 42, height: 16),
      const Radius.circular(3),
    );
    canvas.drawRRect(timeRect, Paint()..color = const Color(0xFF00BCD4));
    final timeTp = TextPainter(
      text: TextSpan(text: '$time', style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    timeTp.paint(canvas, Offset(cx - timeTp.width / 2, topPad + chartHeight + 14 - timeTp.height / 2));

    // Dot at crosshair point
    canvas.drawCircle(Offset(cx, cy), 4, Paint()..color = const Color(0xFF00BCD4));
    canvas.drawCircle(Offset(cx, cy), 2, Paint()..color = Colors.white);
  }

  /// "2026-04-29 09:35:00" → "09:35"
  String _shortTime(String raw) {
    if (raw.length >= 16 && raw.contains(' ')) {
      return raw.split(' ').last.substring(0, 5);
    }
    if (raw.length >= 5) return raw.substring(0, 5);
    return raw;
  }

  @override
  bool shouldRepaint(covariant _TrendPainter oldDelegate) {
    return oldDelegate.points != points ||
        oldDelegate.prevClose != prevClose ||
        oldDelegate.crosshairIndex != crosshairIndex ||
        oldDelegate.crosshairPos != crosshairPos;
  }
}
