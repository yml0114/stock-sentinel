import 'dart:math';
import 'package:flutter/material.dart';

/// 专业K线图组件 v9 — 同花顺级别
/// 成交量柱 + MA5/MA10/MA20 + 十字光标 + 双指缩放 + 单指拖动
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
        height: 360,
        child: Center(
          child: Text('暂无K线数据', style: TextStyle(color: Colors.white.withOpacity(0.4))),
        ),
      );
    }

    return Column(
      children: [
        _buildCrosshairInfo(),
        // K线区域
        SizedBox(
          height: 220,
          child: GestureDetector(
            onScaleStart: (details) {
              _baseScale = _scale;
              _active = true;
            },
            onScaleUpdate: (details) {
              if (details.pointerCount == 1) {
                _updateCrosshair(details.localFocalPoint);
              } else if (details.pointerCount >= 2) {
                _scale = (_baseScale * details.scale).clamp(0.5, 5.0);
              }
              setState(() {});
            },
            onScaleEnd: (_) {
              _active = false;
              Future.delayed(const Duration(milliseconds: 800), () {
                if (!_active && mounted) {
                  setState(() => _crosshairIndex = null);
                }
              });
            },
            behavior: HitTestBehavior.opaque,
            child: ClipRect(
              child: RepaintBoundary(
                child: CustomPaint(
                  size: const Size(double.infinity, 220),
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
        ),
        // 成交量区域
        SizedBox(
          height: 60,
          child: ClipRect(
            child: RepaintBoundary(
              child: CustomPaint(
                size: const Size(double.infinity, 60),
                painter: _VolumePainter(
                  data: widget.data,
                  scale: _scale,
                  crosshairIndex: _crosshairIndex,
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


/// K线蜡烛图 + MA均线
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
    const bottomPad = 4.0;
    final chartWidth = size.width - leftPad - rightPad;
    final chartHeight = size.height - topPad - bottomPad;

    final visibleCount = (data.length / scale).round().clamp(6, data.length);
    final startIdx = (data.length - visibleCount).clamp(0, data.length);
    final visible = data.sublist(startIdx);

    // 计算价格范围（含MA线）
    double minP = double.infinity, maxP = -double.infinity;
    for (final d in visible) {
      final low = (d['low'] as num?)?.toDouble() ?? 0;
      final high = (d['high'] as num?)?.toDouble() ?? 0;
      if (low < minP) minP = low;
      if (high > maxP) maxP = high;
    }

    // 计算MA线范围
    final ma5 = _calcMA(data, 5, startIdx, visible.length);
    final ma10 = _calcMA(data, 10, startIdx, visible.length);
    final ma20 = _calcMA(data, 20, startIdx, visible.length);
    for (final v in [...ma5, ...ma10, ...ma20]) {
      if (v > 0 && v < minP) minP = v;
      if (v > 0 && v > maxP) maxP = v;
    }

    final range = maxP - minP;
    final padding = range * 0.1;
    minP -= padding;
    maxP += padding;
    if (maxP <= minP) maxP = minP + 1;

    double priceToY(double price) => topPad + chartHeight * (1 - (price - minP) / (maxP - minP));
    final gap = chartWidth / visible.length;

    // 网格
    _drawGrid(canvas, size, leftPad, topPad, chartWidth, chartHeight, minP, maxP);

    // 画K线蜡烛
    for (int i = 0; i < visible.length; i++) {
      final d = visible[i];
      final open = (d['open'] as num?)?.toDouble() ?? 0;
      final close = (d['close'] as num?)?.toDouble() ?? 0;
      final high = (d['high'] as num?)?.toDouble() ?? 0;
      final low = (d['low'] as num?)?.toDouble() ?? 0;
      final x = leftPad + gap * i + gap / 2;
      final isUp = close >= open;
      final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);
      final candleW = (gap * 0.6).clamp(2.0, 14.0);

      // 影线
      canvas.drawLine(Offset(x, priceToY(high)), Offset(x, priceToY(low)),
          Paint()..color = color..strokeWidth = 1);

      // 实体
      final bodyTop = priceToY(max(open, close));
      final bodyBottom = priceToY(min(open, close));
      final bodyH = (bodyBottom - bodyTop).clamp(1.0, double.infinity);
      if (isUp) {
        canvas.drawRect(Rect.fromLTWH(x - candleW / 2, bodyTop, candleW, bodyH),
            Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 1);
      } else {
        canvas.drawRect(Rect.fromLTWH(x - candleW / 2, bodyTop, candleW, bodyH),
            Paint()..color = color..style = PaintingStyle.fill);
      }
    }

    // MA均线
    _drawMA(canvas, visible, ma5, leftPad, gap, priceToY, const Color(0xFFFFD700), 1.0);
    _drawMA(canvas, visible, ma10, leftPad, gap, priceToY, const Color(0xFF00BCD4), 1.0);
    _drawMA(canvas, visible, ma20, leftPad, gap, priceToY, const Color(0xFFFF69B4), 1.0);

    // MA图例
    _drawLegend(canvas, size, leftPad);

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

  List<double> _calcMA(List<Map<String, dynamic>> allData, int period, int start, int length) {
    final result = <double>[];
    for (int i = 0; i < length; i++) {
      final globalIdx = start + i;
      if (globalIdx < period - 1) {
        result.add(0);
        continue;
      }
      double sum = 0;
      for (int j = globalIdx - period + 1; j <= globalIdx; j++) {
        sum += (allData[j]['close'] as num?)?.toDouble() ?? 0;
      }
      result.add(sum / period);
    }
    return result;
  }

  void _drawMA(Canvas canvas, List<Map<String, dynamic>> visible, List<double> ma,
      double leftPad, double gap, double Function(double) priceToY, Color color, double width) {
    final path = Path();
    bool started = false;
    for (int i = 0; i < ma.length; i++) {
      if (ma[i] <= 0) continue;
      final x = leftPad + gap * i + gap / 2;
      final y = priceToY(ma[i]);
      if (!started) { path.moveTo(x, y); started = true; } else { path.lineTo(x, y); }
    }
    canvas.drawPath(path, Paint()..color = color..strokeWidth = width..style = PaintingStyle.stroke);
  }

  void _drawLegend(Canvas canvas, Size size, double leftPad) {
    final legends = [
      {'label': 'MA5', 'color': const Color(0xFFFFD700)},
      {'label': 'MA10', 'color': const Color(0xFF00BCD4)},
      {'label': 'MA20', 'color': const Color(0xFFFF69B4)},
    ];
    double x = leftPad;
    for (final l in legends) {
      final tp = TextPainter(
        text: TextSpan(text: l['label'] as String, style: TextStyle(color: l['color'] as Color, fontSize: 9)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(x, 2));
      x += tp.width + 12;
    }
  }

  void _drawGrid(Canvas canvas, Size size, double leftPad, double topPad,
      double chartWidth, double chartHeight, double minP, double maxP) {
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
    final d = data[visIdx];
    final cx = leftPad + gap * visIdx + gap / 2;
    final close = (d['close'] as num?)?.toDouble() ?? 0;
    final cy = priceToY(close);
    final crossPaint = Paint()..color = Colors.white.withOpacity(0.3)..strokeWidth = 0.5;
    canvas.drawLine(Offset(leftPad, cy), Offset(size.width - rightPad, cy), crossPaint);
    canvas.drawLine(Offset(cx, topPad), Offset(cx, topPad + chartHeight), crossPaint);
    // 价格标签
    final priceRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(size.width - 28, cy), width: 56, height: 18), const Radius.circular(4));
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
      Rect.fromCenter(center: Offset(cx, topPad + chartHeight - 8), width: 50, height: 16), const Radius.circular(3));
    canvas.drawRRect(dateRect, Paint()..color = const Color(0xFF4A90D9));
    final dateTp = TextPainter(
      text: TextSpan(text: shortDate, style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    dateTp.paint(canvas, Offset(cx - dateTp.width / 2, topPad + chartHeight - 8 - dateTp.height / 2));
    canvas.drawCircle(Offset(cx, cy), 4, Paint()..color = const Color(0xFF4A90D9));
    canvas.drawCircle(Offset(cx, cy), 2, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(covariant _KlinePainter oldDelegate) {
    return oldDelegate.data != data || oldDelegate.crosshairIndex != crosshairIndex || oldDelegate.scale != scale;
  }
}


/// 成交量柱状图
class _VolumePainter extends CustomPainter {
  final List<Map<String, dynamic>> data;
  final double scale;
  final int? crosshairIndex;

  _VolumePainter({required this.data, this.scale = 1.0, this.crosshairIndex});

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    const leftPad = 40.0;
    const rightPad = 50.0;
    final chartWidth = size.width - leftPad - rightPad;

    final visibleCount = (data.length / scale).round().clamp(6, data.length);
    final startIdx = (data.length - visibleCount).clamp(0, data.length);
    final visible = data.sublist(startIdx);

    double maxVol = 0;
    for (final d in visible) {
      final v = (d['volume'] as num?)?.toDouble() ?? 0;
      if (v > maxVol) maxVol = v;
    }
    if (maxVol <= 0) maxVol = 1;

    final gap = chartWidth / visible.length;
    final barW = (gap * 0.6).clamp(2.0, 14.0);

    for (int i = 0; i < visible.length; i++) {
      final d = visible[i];
      final vol = (d['volume'] as num?)?.toDouble() ?? 0;
      final open = (d['open'] as num?)?.toDouble() ?? 0;
      final close = (d['close'] as num?)?.toDouble() ?? 0;
      final isUp = close >= open;
      final color = isUp ? const Color(0xFFEF4444).withOpacity(0.7) : const Color(0xFF22C55E).withOpacity(0.7);

      final x = leftPad + gap * i + gap / 2;
      final barH = (vol / maxVol) * (size.height - 4);
      canvas.drawRect(
        Rect.fromLTWH(x - barW / 2, size.height - barH, barW, barH),
        Paint()..color = color,
      );
    }

    // 十字光标成交量
    if (crosshairIndex != null) {
      final visIdx = crosshairIndex! - startIdx;
      if (visIdx >= 0 && visIdx < visible.length) {
        final vol = (visible[visIdx]['volume'] as num?)?.toDouble() ?? 0;
        final volText = vol >= 1e8 ? '${(vol / 1e8).toStringAsFixed(1)}亿' :
                       vol >= 1e4 ? '${(vol / 1e4).toStringAsFixed(0)}万' :
                       vol.toStringAsFixed(0);
        final tp = TextPainter(
          text: TextSpan(text: volText, style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 9)),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(leftPad + 4, 2));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _VolumePainter oldDelegate) {
    return oldDelegate.data != data || oldDelegate.crosshairIndex != crosshairIndex || oldDelegate.scale != scale;
  }
}
