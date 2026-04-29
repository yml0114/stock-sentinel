import 'dart:math';
import 'package:flutter/material.dart';

/// 专业K线图组件 v2 — 单指拖动十字光标 + 双指缩放 + 按钮缩放
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
  double _scale = 1.0;
  double _offset = 0;
  int? _crosshairIndex;
  Offset? _crosshairPos;
  double _baseScale = 1.0;
  bool _isDragging = false;

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
        // 十字光标信息栏
        _buildCrosshairInfo(),
        // K线主图
        SizedBox(
          height: 300,
          child: ClipRect(
            child: GestureDetector(
              // ━━ 单指拖动 = 十字光标跟随 ━━
              onHorizontalDragStart: (details) {
                _isDragging = true;
                _updateCrosshair(details.localPosition);
                setState(() {});
              },
              onHorizontalDragUpdate: (details) {
                if (_isDragging) {
                  _updateCrosshair(details.localPosition);
                  setState(() {});
                }
              },
              onHorizontalDragEnd: (_) {
                _isDragging = false;
                Future.delayed(const Duration(milliseconds: 800), () {
                  if (!_isDragging && mounted) {
                    setState(() {
                      _crosshairIndex = null;
                      _crosshairPos = null;
                    });
                  }
                });
              },
              // ━━ 长按十字光标 ━━
              onLongPressStart: (details) {
                _isDragging = true;
                _updateCrosshair(details.localPosition);
                setState(() {});
              },
              onLongPressMoveUpdate: (details) {
                _updateCrosshair(details.localPosition);
                setState(() {});
              },
              onLongPressEnd: (_) {
                _isDragging = false;
                setState(() {
                  _crosshairIndex = null;
                  _crosshairPos = null;
                });
              },
              // ━━ 双指缩放 ━━
              onScaleStart: (details) {
                _baseScale = _scale;
              },
              onScaleUpdate: (details) {
                if (details.pointerCount >= 2) {
                  setState(() {
                    _scale = (_baseScale * details.scale).clamp(0.5, 5.0);
                  });
                }
              },
              child: CustomPaint(
                size: const Size(double.infinity, 300),
                painter: _KlinePainter(
                  data: widget.data,
                  scale: _scale,
                  offset: _offset,
                  crosshairIndex: _crosshairIndex,
                  crosshairPos: _crosshairPos,
                  currencySymbol: widget.currencySymbol,
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
              GestureDetector(
                onTap: () => setState(() => _scale = (_scale * 0.8).clamp(0.5, 5.0)),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.06),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text('−', style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 18)),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '${(_scale * 100).round()}%',
                style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12),
              ),
              const SizedBox(width: 12),
              GestureDetector(
                onTap: () => setState(() => _scale = (_scale * 1.25).clamp(0.5, 5.0)),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.06),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text('+', style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 18)),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _updateCrosshair(Offset localPos) {
    final size = context.size;
    if (size == null) return;
    final chartHeight = size.height * 0.65;
    if (localPos.dy < 0 || localPos.dy > chartHeight) return;

    final visibleCount = (widget.data.length / _scale).round().clamp(5, widget.data.length);
    final startX = (widget.data.length - visibleCount - (_offset / 2).round()).clamp(0, widget.data.length - visibleCount);
    final idx = startX + (localPos.dx / size.width * visibleCount).round();
    if (idx >= 0 && idx < widget.data.length) {
      _crosshairIndex = idx;
      _crosshairPos = localPos;
    }
  }

  Widget _buildCrosshairInfo() {
    if (widget.data.isEmpty) return const SizedBox.shrink();

    final Map<String, dynamic> d;
    if (_crosshairIndex != null && _crosshairIndex! >= 0 && _crosshairIndex! < widget.data.length) {
      d = widget.data[_crosshairIndex!];
    } else {
      d = widget.data.last;
    }

    final open = (d['open'] as num?)?.toDouble() ?? 0;
    final close = (d['close'] as num?)?.toDouble() ?? 0;
    final high = (d['high'] as num?)?.toDouble() ?? 0;
    final low = (d['low'] as num?)?.toDouble() ?? 0;
    final vol = (d['volume'] as num?)?.toDouble() ?? 0;
    final isUp = close >= open;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      color: _crosshairIndex != null ? Colors.white.withOpacity(0.03) : null,
      child: Row(
        children: [
          Text('${d['date'] ?? ''}', style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(width: 8),
          _infoTag('开', open, isUp),
          _infoTag('收', close, isUp),
          _infoTag('高', high, isUp),
          _infoTag('低', low, isUp),
          _infoTag('量', _formatVolume(vol), isUp, isVol: true),
        ],
      ),
    );
  }

  Widget _infoTag(String label, dynamic value, bool isUp, {bool isVol = false}) {
    final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);
    final text = isVol ? value.toString() : '${widget.currencySymbol}${(value as double).toStringAsFixed(2)}';
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Text.rich(
        TextSpan(children: [
          TextSpan(text: '$label:', style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 11)),
          TextSpan(text: text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
        ]),
      ),
    );
  }

  String _formatVolume(double vol) {
    if (vol >= 1e8) return '${(vol / 1e8).toStringAsFixed(1)}亿';
    if (vol >= 1e4) return '${(vol / 1e4).toStringAsFixed(0)}万';
    return vol.toStringAsFixed(0);
  }
}


class _KlinePainter extends CustomPainter {
  final List<Map<String, dynamic>> data;
  final double scale;
  final double offset;
  final int? crosshairIndex;
  final Offset? crosshairPos;
  final String currencySymbol;

  _KlinePainter({
    required this.data,
    required this.scale,
    required this.offset,
    this.crosshairIndex,
    this.crosshairPos,
    this.currencySymbol = '¥',
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    final chartHeight = size.height * 0.65;
    final volHeight = size.height * 0.25;
    final volTop = chartHeight + 4;

    final visibleCount = (data.length / scale).round().clamp(5, data.length);
    final startX = (data.length - visibleCount - (offset / 2).round()).clamp(0, data.length - visibleCount);
    final endIdx = (startX + visibleCount).clamp(0, data.length);
    final visible = data.sublist(startX, endIdx);

    if (visible.isEmpty) return;

    double minPrice = double.infinity;
    double maxPrice = -double.infinity;
    double maxVol = 0;
    for (final d in visible) {
      final low = (d['low'] as num?)?.toDouble() ?? 0;
      final high = (d['high'] as num?)?.toDouble() ?? 0;
      final vol = (d['volume'] as num?)?.toDouble() ?? 0;
      if (low < minPrice) minPrice = low;
      if (high > maxPrice) maxPrice = high;
      if (vol > maxVol) maxVol = vol;
    }

    final pricePadding = (maxPrice - minPrice) * 0.05;
    minPrice -= pricePadding;
    maxPrice += pricePadding;
    if (maxPrice == minPrice) maxPrice = minPrice + 1;

    final candleWidth = size.width / visibleCount;
    final bodyWidth = candleWidth * 0.7;

    _drawGrid(canvas, size, chartHeight, minPrice, maxPrice, volTop);
    _drawMA(canvas, size, startX, endIdx, chartHeight, minPrice, maxPrice, candleWidth);

    for (int i = 0; i < visible.length; i++) {
      final d = visible[i];
      final open = (d['open'] as num?)?.toDouble() ?? 0;
      final close = (d['close'] as num?)?.toDouble() ?? 0;
      final high = (d['high'] as num?)?.toDouble() ?? 0;
      final low = (d['low'] as num?)?.toDouble() ?? 0;
      final vol = (d['volume'] as num?)?.toDouble() ?? 0;

      final isUp = close >= open;
      final color = isUp ? const Color(0xFFEF4444) : const Color(0xFF22C55E);

      final cx = i * candleWidth + candleWidth / 2;

      final highY = chartHeight * (1 - (high - minPrice) / (maxPrice - minPrice));
      final lowY = chartHeight * (1 - (low - minPrice) / (maxPrice - minPrice));
      canvas.drawLine(Offset(cx, highY), Offset(cx, lowY), Paint()..color = color..strokeWidth = 1);

      final top = max(open, close);
      final bottom = min(open, close);
      final topY = chartHeight * (1 - (top - minPrice) / (maxPrice - minPrice));
      final bottomY = chartHeight * (1 - (bottom - minPrice) / (maxPrice - minPrice));
      final bodyH = (bottomY - topY).abs().clamp(1.0, chartHeight);

      final bodyRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(cx, (topY + bottomY) / 2), width: bodyWidth, height: bodyH),
        const Radius.circular(1),
      );

      final bodyPaint = Paint()..color = color;
      if (isUp) {
        bodyPaint.style = PaintingStyle.stroke;
        bodyPaint.strokeWidth = 1.5;
      }
      canvas.drawRRect(bodyRect, bodyPaint);

      if (maxVol > 0) {
        final volBarH = (vol / maxVol * volHeight).clamp(1.0, volHeight);
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromLTWH(cx - bodyWidth / 2, size.height - volBarH, bodyWidth, volBarH),
            const Radius.circular(1),
          ),
          Paint()..color = color.withOpacity(0.6),
        );
      }
    }

    _drawPriceLabels(canvas, size, chartHeight, minPrice, maxPrice);
    _drawDateLabels(canvas, size, visible, candleWidth, chartHeight);

    if (crosshairIndex != null && crosshairPos != null) {
      _drawCrosshair(canvas, size, chartHeight, crosshairIndex! - startX, candleWidth, minPrice, maxPrice, visible);
    }
  }

  void _drawGrid(Canvas canvas, Size size, double chartHeight, double minPrice, double maxPrice, double volTop) {
    final gridPaint = Paint()..color = Colors.white.withOpacity(0.04)..strokeWidth = 0.5;
    for (int i = 0; i <= 4; i++) {
      final y = chartHeight * i / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
    canvas.drawLine(Offset(0, volTop), Offset(size.width, volTop), gridPaint);
  }

  void _drawMA(Canvas canvas, Size size, int startIdx, int endIdx, double chartHeight, double minPrice, double maxPrice, double candleWidth) {
    final maColors = {
      5: const Color(0xFFFFD700),
      10: const Color(0xFF00BFFF),
      20: const Color(0xFFFF69B4),
      60: const Color(0xFF9370DB),
    };

    for (final entry in maColors.entries) {
      final period = entry.key;
      final path = Path();
      bool started = false;

      for (int i = startIdx; i < endIdx; i++) {
        if (i < period - 1) continue;
        double sum = 0;
        for (int j = i - period + 1; j <= i; j++) {
          sum += (data[j]['close'] as num?)?.toDouble() ?? 0;
        }
        final ma = sum / period;
        final x = (i - startIdx) * candleWidth + candleWidth / 2;
        final y = chartHeight * (1 - (ma - minPrice) / (maxPrice - minPrice));
        if (!started) { path.moveTo(x, y); started = true; } else { path.lineTo(x, y); }
      }

      canvas.drawPath(path, Paint()..color = entry.value.withOpacity(0.7)..strokeWidth = 1..style = PaintingStyle.stroke);
    }
  }

  void _drawPriceLabels(Canvas canvas, Size size, double chartHeight, double minPrice, double maxPrice) {
    for (int i = 0; i <= 4; i++) {
      final price = maxPrice - (maxPrice - minPrice) * i / 4;
      final y = chartHeight * i / 4;
      final tp = TextPainter(
        text: TextSpan(text: price.toStringAsFixed(2), style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 10)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(size.width - tp.width - 4, y - tp.height / 2));
    }
  }

  void _drawDateLabels(Canvas canvas, Size size, List<Map<String, dynamic>> visible, double candleWidth, double chartHeight) {
    final interval = (visible.length / 4).round().clamp(1, visible.length);
    for (int i = 0; i < visible.length; i += interval) {
      final date = visible[i]['date'] as String? ?? '';
      final parts = date.split('-');
      final label = parts.length >= 3 ? '${parts[1]}/${parts[2]}' : date;
      final x = i * candleWidth + candleWidth / 2;
      final tp = TextPainter(
        text: TextSpan(text: label, style: TextStyle(color: Colors.white.withOpacity(0.3), fontSize: 10)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(x - tp.width / 2, chartHeight + 8));
    }
  }

  void _drawCrosshair(Canvas canvas, Size size, double chartHeight, int localIdx, double candleWidth, double minPrice, double maxPrice, List<Map<String, dynamic>> visible) {
    if (localIdx < 0 || localIdx >= visible.length) return;

    final cx = localIdx * candleWidth + candleWidth / 2;
    final close = (visible[localIdx]['close'] as num?)?.toDouble() ?? 0;
    final cy = chartHeight * (1 - (close - minPrice) / (maxPrice - minPrice));

    final crossPaint = Paint()..color = Colors.white.withOpacity(0.3)..strokeWidth = 0.5;
    canvas.drawLine(Offset(0, cy), Offset(size.width, cy), crossPaint);
    canvas.drawLine(Offset(cx, 0), Offset(cx, chartHeight), crossPaint);

    final priceRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: Offset(size.width - 30, cy), width: 60, height: 18),
      const Radius.circular(4),
    );
    canvas.drawRRect(priceRect, Paint()..color = const Color(0xFF4A90D9));
    final tp = TextPainter(
      text: TextSpan(text: close.toStringAsFixed(2), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w600)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(size.width - 30 - tp.width / 2, cy - tp.height / 2));

    canvas.drawCircle(Offset(cx, cy), 3, Paint()..color = const Color(0xFF4A90D9));
  }

  @override
  bool shouldRepaint(covariant _KlinePainter oldDelegate) {
    return oldDelegate.data != data || oldDelegate.scale != scale || oldDelegate.offset != offset || oldDelegate.crosshairIndex != crosshairIndex;
  }
}
