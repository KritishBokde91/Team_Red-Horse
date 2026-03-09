import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';

/// Horizontal bar chart showing supports vs refutes vs neutral counts.
class StanceChart extends StatelessWidget {
  final int supports;
  final int refutes;
  final int neutral;

  const StanceChart({
    super.key,
    required this.supports,
    required this.refutes,
    required this.neutral,
  });

  @override
  Widget build(BuildContext context) {
    final total = supports + refutes + neutral;
    if (total == 0) return const SizedBox.shrink();

    return Container(
      decoration: NeoDeco.card(),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'STANCE BREAKDOWN',
            style: GoogleFonts.spaceGrotesk(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: NeoColors.muted,
              letterSpacing: 2,
            ),
          ),
          const SizedBox(height: 16),
          // Bar
          Container(
            height: 28,
            decoration: BoxDecoration(
              border: Border.all(color: NeoColors.border, width: 2),
            ),
            child: Row(
              children: [
                if (supports > 0)
                  Flexible(
                    flex: supports,
                    child: Container(color: NeoColors.verified),
                  ),
                if (refutes > 0)
                  Flexible(
                    flex: refutes,
                    child: Container(color: NeoColors.fake),
                  ),
                if (neutral > 0)
                  Flexible(
                    flex: neutral,
                    child: Container(color: NeoColors.mutedLight),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          // Legend
          Row(
            children: [
              _buildLegend('Supports', supports, NeoColors.verified),
              const SizedBox(width: 16),
              _buildLegend('Refutes', refutes, NeoColors.fake),
              const SizedBox(width: 16),
              _buildLegend('Neutral', neutral, NeoColors.muted),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLegend(String label, int count, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            border: Border.all(color: NeoColors.border, width: 1),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '$count $label',
          style: GoogleFonts.inter(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: NeoColors.charcoal,
          ),
        ),
      ],
    );
  }
}
