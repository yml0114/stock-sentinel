import 'dart:math';
import 'package:flutter/material.dart';

/// 分时走势线组件 v8
/// 核心：只用 onScale*（不能和 onPan* 共存！）
/// 单指 = 拖动十字光标，双指 = 缩放，+/− 按钮辅助
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
  double _scale = 1.0;
  double _baseScale = 1.0;
  bool _active = false;

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
        _buildCrosshairInfo(),
        SizedBox(
          height: 250,
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
                _scale = (_baseScale * details.scale).clamp(0.5, 3.0);
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
                size: const Size(double.infinity, 250),
                painter: _TrendPainter(
                  points: _points,
                  prevClose: _prevClose,
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
              _scaleBtn(Icons.remove, () => setState(() => _scale = (_scale * 0.75).clamp(0.5, 3.0))),
              const SizedBox(width: 6),
              Text('${(_scale * 100).round()}%', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11)),
              const SizedBox(width: 6),
              _scaleBtn(Icons.add, () => setState(() => _scale = (_scale * 1.33).clamp(0.5, 3.0))),
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
    final count = _points.length;
    if (count == 0) return;

    const leftPad = 40.0;
    const rightPad = 50.0;
    final w = context.size?.width ?? 400;
    final chartWidth = w - leftPad - rightPad;
    if (localPos.dx < leftPad || localPos.dx > leftPad + chartWidth) return;

    final idx = ((localPos.dx - leftPad) / chartWidth * (count - 1)).round().clamp(0, count - 1);
    _crosshairIndex = idx;
  }

  Widget _buildCrosshairInfo() {
    if (_crosshairIndex == null || _crosshairIndex! >= _points.length) {
      if (_points.isEmpty) return const SizedBox.shrink();
      final p = _points.last;
      final price = (p['price'] as num?)?.toDouble() ?? 0;
      final change = price - _prevClose;
      final changePct = _prevClose > 0 ? change / _prevClose * 100 : 0;
      final isUp = change >= 0;
      final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Row(
          children: [
            Text('滑动查看', style: TextStyle(color: Colors.white.withOpacity(0.2), fontSize: 11)),
            const Spacer(),
            Text('${widget.currencySymbol}${price.toStringAsFixed(2)}',
                style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            Text('${isUp ? "+" : ""}${changePct.toStringAsFixed(2)}%',
                style: TextStyle(color: color, fontSize: 11)),
          ],
        ),
      );
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
          Text(time, style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(width: 8),
          _tag('价', '${widget.currencySymbol}${price.toStringAsFixed(2)}', color),
          _tag('均', '${widget.currencySymbol}${avg.toStringAsFixed(2)}', const Color(0xFFFFD700)),
          _tag('幅', '${isUp ? "+" : ""}${changePct.toStringAsFixed(2)}%', color),
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

  String _shortenTime(String raw) {
    if (raw.length >= 16 && raw.contains(' ')) return raw.split(' ').last.substring(0, 5);
    if (raw.length >= 5) return raw.substring(0, 5);
    return raw;
  }
}


class _TrendPainter extends CustomPainter {
  final List<Map<String, dynamic>> points;
  final double prevClose;
  final String currencySymbol;
  final int? crosshairIndex;
  final double scale;

  _TrendPainter({
    required this.points,
    required this.prevClose,
    this.currencySymbol = '¥',
    this.crosshairIndex,
    this.scale = 1.0,
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

    final visibleCount = (points.length / scale).round().clamp(10, points.length);
    final startIdx = (points.length - visibleCount).clamp(0, points.length);
    final visible = points.sublist(startIdx);

    final prices = visible.map((p) => (p['price'] as num?)?.toDouble() ?? 0).toList();
    final avgs = visible.map((p) => (p['avg_price'] as num?)?.toDouble() ?? 0).toList();

    double minP = prices.reduce(min);
    double maxP = prices.reduce(max);

    for (final a in avgs) {
      if (a > 0) {
        if (a < minP) minP = a;
        if (a > maxP) maxP = a;
      }
    }
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
      return leftPad + chartWidth * i / (visible.length - 1).clamp(1, visible.length);
    }

    _drawGrid(canvas, size, leftPad, topPad, chartWidth, chartHeight, minP, maxP, bottomPad, visible, indexToX);

    if (prevClose > 0) {
      final pcY = priceToY(prevClose);
      final dashPaint = Paint()
        ..color = Colors.white.withOpacity(0.35)
        ..strokeWidth = 0.8
        ..style = PaintingStyle.stroke;
      _drawDashedLine(canvas, Offset(leftPad, pcY), Offset(size.width - rightPad, pcY), dashPaint);
      final tp = TextPainter(
        text: TextSpan(text: '昨收', style: TextStyle(color: Colors.white.withOpacity(0.35), fontSize: 9)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(size.width - rightPad + 4, pcY - tp.height / 2));
    }

    final pricePath = Path();
    for (int i = 0; i < visible.length; i++) {
      final x = indexToX(i);
      final y = priceToY(prices[i]);
      if (i == 0) {
        pricePath.moveTo(x, y);
      } else {
        final prevX = indexToX(i - 1);
        final prevY = priceToY(prices[i - 1]);
        final cpX = (prevX + x) / 2;
        pricePath.quadraticBezierTo(cpX, prevY, x, y);
      }
    }

    final fillPath = Path.from(pricePath);
    fillPath.lineTo(indexToX(visible.length - 1), topPad + chartHeight);
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

    canvas.drawPath(pricePath, Paint()
      ..color = const Color(0xFF00BCD4)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke);

    final avgPath = Path();
    bool avgStarted = false;
    for (int i = 0; i < visible.length; i++) {
      if (avgs[i] <= 0) continue;
      final x = indexToX(i);
      final y = priceToY(avgs[i]);
      if (!avgStarted) { avgPath.moveTo(x, y); avgStarted = true; } else { avgPath.lineTo(x, y); }
    }
    canvas.drawPath(avgPath, Paint()
      ..color = const Color(0xFFFFD700).withOpacity(0.8)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke);

    final lastX = indexToX(visible.length - 1);
    final lastY = priceToY(prices.last);
    canvas.drawCircle(Offset(lastX, lastY), 3, Paint()..color = const Color(0xFF00BCD4));

    _drawTimeLabels(canvas, size, topPad, chartHeight, leftPad, rightPad, bottomPad, visible, indexToX);
    _drawPriceLabels(canvas, size, leftPad, topPad, chartHeight, minP, maxP);

    if (crosshairIndex != null) {
      final visIdx = crosshairIndex! - startIdx;
      if (visIdx >= 0 && visIdx < visible.length) {
        _drawCrosshair(canvas, size, chartHeight, topPad, leftPad, rightPad, priceToY, indexToX, visIdx);
      }
    }
  }

  void _drawGrid(Canvas canvas, Size size, double leftPad, double topPad,
      double chartWidth, double chartHeight, double minP, double maxP, double bottomPad,
      List<Map<String, dynamic>> visible, double Function(int) indexToX) {
    final gridPaint = Paint()..color = Colors.white.withOpacity(0.04)..strokeWidth = 0.5;
    for (int i = 0; i <= 4; i++) {
      final y = topPad + chartHeight * i / 4;
      canvas.drawLine(Offset(leftPad, y), Offset(size.width - 50, y), gridPaint);
    }
    for (int i = 0; i < visible.length; i++) {
      final t = _shortTime(visible[i]['time'] ?? '');
      if (t == '09:30' || t == '10:30' || t == '11:30' || t == '13:00' || t == '14:00' || t == '15:00') {
        final x = indexToX(i);
        canvas.drawLine(Offset(x, topPad), Offset(x, topPad + chartHeight), gridPaint);
      }
    }
  }

  void _drawTimeLabels(Canvas canvas, Size size, double topPad, double chartHeight,
      double leftPad, double rightPad, double bottomPad,
      List<Map<String, dynamic>> visible, double Function(int) indexToX) {
    final keyTimes = ['09:30', '10:30', '11:30', '13:00', '14:00', '15:00'];
    for (int i = 0; i < visible.length; i++) {
      final t = _shortTime(visible[i]['time'] ?? '');
      if (!keyTimes.contains(t)) continue;
      final ki = keyTimes.indexOf(t);
      if (ki % 2 != 0 && ki != keyTimes.length - 1) continue;
      final x = indexToX(i);
      final tp = TextPainter(
        text: TextSpan(text: t, style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9)),
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
        text: TextSpan(text: price.toStringAsFixed(2), style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 9)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(2, y - tp.height / 2));
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

  void _drawDashedLine(Canvas canvas, Offset start, Offset end, Paint paint,
      {double dashWidth = 4, double dashSpace = 3}) {
    final dx = end.dx - start.dx;
    final dy = end.dy - start.dy;
    final distance = sqrt(dx * dx + dy * dy);
    if (distance == 0) return;
    final count = (distance / (dashWidth + dashSpace)).floor();
    final unitDx = dx / distance;
    final unitDy = dy / distance;
    for (int i = 0; i < count; i++) {
      final sx = start.dx + unitDx * (dashWidth + dashSpace) * i;
      final sy = start.dy + unitDy * (dashWidth + dashSpace) * i;
      canvas.drawLine(Offset(sx, sy), Offset(sx + unitDx * dashWidth, sy + unitDy * dashWidth), paint);
    }
  }

  void _drawCrosshair(Canvas canvas, Size size, double chartHeight, double topPad,
      double leftPad, double rightPad, double Function(double) priceToY,
      double Function(int) indexToX, int localIdx) {
    if (localIdx < 0 || localIdx >= points.length) return;

    final cx = indexToX(localIdx);
    final price = (points[localIdx]['price'] as num?)?.toDouble() ?? 0;
    final cy = priceToY(price);

    final crossPaint = Paint()..color = Colors.white.withOpacity(0.3)..strokeWidth = 0.5;
    canvas.drawLine(Offset(leftPad, cy), Offset(size.width - rightPad, cy), crossPaint);
    canvas.drawLine(Offset(cx, topPad), Offset(cx, topPad + chartHeight), crossPaint);

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

    final time = _shortTime(points[localIdx]['time'] ?? '');
    final timeRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(cx, topPad + chartHeight + 14), width: 42, height: 16),
      const Radius.circular(3),
    );
    canvas.drawRRect(timeRect, Paint()..color = const Color(0xFF00BCD4));
    final timeTp = TextPainter(
      text: TextSpan(text: time, style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    timeTp.paint(canvas, Offset(cx - timeTp.width / 2, topPad + chartHeight + 14 - timeTp.height / 2));

    canvas.drawCircle(Offset(cx, cy), 4, Paint()..color = const Color(0xFF00BCD4));
    canvas.drawCircle(Offset(cx, cy), 2, Paint()..color = Colors.white);
  }

  String _shortTime(String raw) {
    if (raw.length >= 16 && raw.contains(' ')) return raw.split(' ').last.substring(0, 5);
    if (raw.length >= 5) return raw.substring(0, 5);
    return raw;
  }

  @override
  bool shouldRepaint(covariant _TrendPainter oldDelegate) {
    return oldDelegate.points != points || oldDelegate.prevClose != prevClose ||
        oldDelegate.crosshairIndex != crosshairIndex || oldDelegate.scale != scale;
  }
}
