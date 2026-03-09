import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';
import '../../data/models/verdict_model.dart';

/// Final verdict display card with neo-brutalism styling.
class VerdictCard extends StatelessWidget {
  final VerdictModel verdict;

  const VerdictCard({super.key, required this.verdict});

  @override
  Widget build(BuildContext context) {
    final (
      verdictColor,
      verdictBg,
      verdictIcon,
      verdictEmoji,
    ) = switch (verdict.verdict) {
      'FAKE' => (NeoColors.fake, NeoColors.fakeLight, Icons.cancel, '🔴'),
      'TRUE' => (
        NeoColors.verified,
        NeoColors.verifiedLight,
        Icons.check_circle,
        '🟢',
      ),
      _ => (NeoColors.unverified, NeoColors.unverifiedLight, Icons.help, '🟡'),
    };

    return Container(
      decoration: BoxDecoration(
        color: verdictBg,
        border: Border.all(color: verdictColor, width: 3),
        boxShadow: [
          BoxShadow(
            color: verdictColor.withValues(alpha: 0.4),
            offset: const Offset(5, 5),
            blurRadius: 0,
          ),
        ],
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Text(
                'VERDICT',
                style: GoogleFonts.spaceGrotesk(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: verdictColor,
                  letterSpacing: 2,
                ),
              ),
              const Spacer(),
              Text(verdictEmoji, style: const TextStyle(fontSize: 24)),
            ],
          ),
          const SizedBox(height: 8),

          // Verdict label
          Text(
            verdict.verdict,
            style: GoogleFonts.spaceGrotesk(
              fontSize: 36,
              fontWeight: FontWeight.w700,
              color: verdictColor,
            ),
          ),
          const SizedBox(height: 4),

          // Claim
          Text(
            '"${verdict.claim}"',
            style: GoogleFonts.inter(
              fontSize: 14,
              fontStyle: FontStyle.italic,
              color: NeoColors.charcoal,
            ),
          ),
          const SizedBox(height: 16),

          // Score row
          Container(
            padding: const EdgeInsets.all(12),
            decoration: NeoDeco.cardFlat(color: NeoColors.surface),
            child: Row(
              children: [
                _buildMetric('Score', verdict.veracityScore.toStringAsFixed(2)),
                Container(width: 2, height: 30, color: NeoColors.mutedLight),
                _buildMetric(
                  'Confidence',
                  '${(verdict.confidence * 100).toInt()}%',
                ),
                Container(width: 2, height: 30, color: NeoColors.mutedLight),
                _buildMetric(
                  'Sources',
                  '${verdict.supports + verdict.refutes + verdict.neutral}',
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Explanation
          Text(
            'ANALYSIS',
            style: GoogleFonts.spaceGrotesk(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: NeoColors.muted,
              letterSpacing: 2,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            verdict.explanation,
            style: GoogleFonts.inter(
              fontSize: 14,
              color: NeoColors.charcoal,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: GoogleFonts.spaceGrotesk(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: NeoColors.charcoal,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 11, color: NeoColors.muted),
          ),
        ],
      ),
    );
  }
}
