import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shimmer/shimmer.dart';
import '../../core/theme.dart';
import '../../data/models/evidence_model.dart';

/// Live evidence list showing search results, scraping status, and stance.
class EvidenceList extends StatelessWidget {
  final List<EvidenceModel> results;
  final List<EvidenceModel> stances;
  final int scrapingIndex;
  final int scrapingTotal;
  final bool isScrapingPhase;

  const EvidenceList({
    super.key,
    required this.results,
    this.stances = const [],
    this.scrapingIndex = 0,
    this.scrapingTotal = 0,
    this.isScrapingPhase = false,
  });

  @override
  Widget build(BuildContext context) {
    if (results.isEmpty) return const SizedBox.shrink();

    return Container(
      decoration: NeoDeco.card(),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'EVIDENCE SOURCES',
                style: GoogleFonts.spaceGrotesk(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: NeoColors.muted,
                  letterSpacing: 2,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: NeoDeco.pill(color: NeoColors.background),
                child: Text(
                  '${results.length}',
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          if (isScrapingPhase && scrapingTotal > 0) ...[
            const SizedBox(height: 12),
            _buildScrapingProgress(),
          ],
          const SizedBox(height: 12),
          ...results.take(10).map(_buildEvidenceItem),
          if (results.length > 10)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                '+${results.length - 10} more sources',
                style: GoogleFonts.inter(fontSize: 13, color: NeoColors.muted),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildScrapingProgress() {
    final progress = scrapingTotal > 0 ? scrapingIndex / scrapingTotal : 0.0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Scraping $scrapingIndex/$scrapingTotal',
              style: GoogleFonts.inter(fontSize: 12, color: NeoColors.muted),
            ),
            const Spacer(),
            Text(
              '${(progress * 100).toInt()}%',
              style: GoogleFonts.spaceGrotesk(
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Container(
          height: 6,
          decoration: BoxDecoration(
            color: NeoColors.mutedLight,
            border: Border.all(color: NeoColors.border, width: 1),
          ),
          child: FractionallySizedBox(
            alignment: Alignment.centerLeft,
            widthFactor: progress,
            child: Container(color: NeoColors.charcoal),
          ),
        ),
      ],
    );
  }

  Widget _buildEvidenceItem(EvidenceModel evidence) {
    // Check if we have stance data for this URL
    final stanceData = stances.where((s) => s.url == evidence.url).firstOrNull;
    final hasStance = stanceData != null && stanceData.stance.isNotEmpty;

    final tierColor = switch (evidence.tier) {
      1 => NeoColors.tier1,
      2 => NeoColors.tier2,
      _ => NeoColors.tier3,
    };

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: NeoDeco.cardFlat(
          color: evidence.failed ? const Color(0xFFFEE2E2) : null,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Tier badge
            Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color: tierColor,
                border: Border.all(color: NeoColors.border, width: 1.5),
              ),
              child: Center(
                child: Text(
                  'T${evidence.tier}',
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
            // Content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    evidence.title.isNotEmpty
                        ? evidence.title
                        : Uri.tryParse(evidence.url)?.host ?? evidence.url,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: NeoColors.charcoal,
                    ),
                  ),
                  if (evidence.scraped || evidence.failed)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Row(
                        children: [
                          Icon(
                            evidence.failed ? Icons.close : Icons.check,
                            size: 12,
                            color: evidence.failed
                                ? NeoColors.fake
                                : NeoColors.verified,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            evidence.failed
                                ? 'Failed'
                                : '${evidence.chars} chars',
                            style: GoogleFonts.inter(
                              fontSize: 11,
                              color: NeoColors.muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
            // Stance indicator
            if (hasStance) _buildStanceBadge(stanceData.stance),
            if (!hasStance && !evidence.failed && evidence.scraped)
              Shimmer.fromColors(
                baseColor: NeoColors.mutedLight,
                highlightColor: NeoColors.background,
                child: Container(
                  width: 50,
                  height: 20,
                  color: NeoColors.mutedLight,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildStanceBadge(String stance) {
    final (color, bg, label) = switch (stance) {
      'SUPPORTS' => (NeoColors.verified, NeoColors.verifiedLight, 'SUP'),
      'REFUTES' => (NeoColors.fake, NeoColors.fakeLight, 'REF'),
      _ => (NeoColors.muted, NeoColors.mutedLight, 'N/A'),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        border: Border.all(color: color, width: 1.5),
      ),
      child: Text(
        label,
        style: GoogleFonts.spaceGrotesk(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}
