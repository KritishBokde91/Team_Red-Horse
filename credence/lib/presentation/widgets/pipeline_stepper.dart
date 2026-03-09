import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';
import '../bloc/verify_state.dart';

/// Animated pipeline stepper that shows progress through the 6 stages.
class PipelineStepper extends StatelessWidget {
  final PipelineStage currentStage;
  final String message;

  const PipelineStepper({
    super.key,
    required this.currentStage,
    required this.message,
  });

  static const _stages = [
    (PipelineStage.claimExtraction, 'Extract Claims', Icons.content_cut),
    (PipelineStage.multiTierSearch, 'Search Sources', Icons.search),
    (PipelineStage.scraping, 'Scrape Evidence', Icons.download),
    (PipelineStage.stanceDetection, 'Analyze Stance', Icons.analytics),
    (PipelineStage.verdict, 'Compute Verdict', Icons.gavel),
    (PipelineStage.explanation, 'Generate Report', Icons.description),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: NeoDeco.card(),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'PIPELINE',
                style: GoogleFonts.spaceGrotesk(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: NeoColors.muted,
                  letterSpacing: 2,
                ),
              ),
              const Spacer(),
              if (currentStage != PipelineStage.completed &&
                  currentStage != PipelineStage.error)
                SpinKitThreeBounce(color: NeoColors.charcoal, size: 16),
            ],
          ),
          const SizedBox(height: 12),
          ..._stages.map((s) => _buildStep(s.$1, s.$2, s.$3)),
          if (message.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: NeoDeco.cardFlat(color: NeoColors.background),
              child: Text(
                message,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  color: NeoColors.muted,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStep(PipelineStage stage, String label, IconData icon) {
    final stageIndex = PipelineStage.values.indexOf(stage);
    final currentIndex = PipelineStage.values.indexOf(currentStage);
    final isActive =
        currentIndex >= stageIndex && currentStage != PipelineStage.idle;
    final isCurrent = currentStage == stage;
    final isDone =
        currentIndex > stageIndex || currentStage == PipelineStage.completed;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: isDone
                  ? NeoColors.charcoal
                  : isCurrent
                  ? NeoColors.charcoal
                  : NeoColors.mutedLight,
              border: Border.all(color: NeoColors.border, width: 2),
            ),
            child: Center(
              child: isDone
                  ? const Icon(Icons.check, size: 14, color: NeoColors.surface)
                  : Icon(
                      icon,
                      size: 14,
                      color: isCurrent ? NeoColors.surface : NeoColors.muted,
                    ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 14,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                color: isActive ? NeoColors.charcoal : NeoColors.muted,
              ),
            ),
          ),
          if (isCurrent) SpinKitPulse(color: NeoColors.charcoal, size: 12),
        ],
      ),
    );
  }
}
