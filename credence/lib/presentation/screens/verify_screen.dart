import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';
import '../bloc/verify_bloc.dart';
import '../bloc/verify_event.dart';
import '../bloc/verify_state.dart';
import '../widgets/claim_input_card.dart';
import '../widgets/pipeline_stepper.dart';
import '../widgets/evidence_list.dart';
import '../widgets/stance_chart.dart';
import '../widgets/verdict_card.dart';
import '../widgets/shield_toggle_card.dart';

/// Main screen of the Credence fact-checker app.
class VerifyScreen extends StatefulWidget {
  const VerifyScreen({super.key});

  @override
  State<VerifyScreen> createState() => _VerifyScreenState();
}

class _VerifyScreenState extends State<VerifyScreen> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onSubmit() {
    final claim = _controller.text.trim();
    if (claim.isEmpty) return;
    context.read<VerifyBloc>().add(SubmitClaim(claim));
  }

  void _onReset() {
    _controller.clear();
    context.read<VerifyBloc>().add(const ResetPipeline());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: BlocBuilder<VerifyBloc, VerifyState>(
          builder: (context, state) {
            return CustomScrollView(
              slivers: [
                // App bar
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                    child: Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: NeoColors.charcoal,
                            border: Border.all(
                              color: NeoColors.border,
                              width: 2,
                            ),
                          ),
                          child: const Center(
                            child: Text(
                              'C',
                              style: TextStyle(
                                color: NeoColors.surface,
                                fontSize: 20,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'CREDENCE',
                          style: GoogleFonts.spaceGrotesk(
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                            color: NeoColors.charcoal,
                            letterSpacing: 3,
                          ),
                        ),
                        const Spacer(),
                        if (!state.isIdle)
                          GestureDetector(
                            onTap: _onReset,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 6,
                              ),
                              decoration: NeoDeco.cardFlat(),
                              child: Text(
                                'NEW',
                                style: GoogleFonts.spaceGrotesk(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 1,
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),

                // Subtitle
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 6, 20, 16),
                    child: Text(
                      'AI-Powered Misinformation Detection',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: NeoColors.muted,
                      ),
                    ),
                  ),
                ),

                // Content
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      // Input card
                      ClaimInputCard(
                        controller: _controller,
                        onSubmit: _onSubmit,
                        isLoading: state.isRunning,
                      ),
                      const SizedBox(height: 16),

                      // Shield toggle
                      const ShieldToggleCard(),
                      const SizedBox(height: 16),

                      // Pipeline stepper (shows when running or done)
                      if (!state.isIdle)
                        PipelineStepper(
                          currentStage: state.stage,
                          message: state.currentStageMessage,
                        ),
                      if (!state.isIdle) const SizedBox(height: 16),

                      // Extracted claims
                      if (state.extractedClaims.isNotEmpty)
                        _buildExtractedClaims(state),
                      if (state.extractedClaims.isNotEmpty)
                        const SizedBox(height: 16),

                      // Evidence list
                      if (state.searchResults.isNotEmpty)
                        EvidenceList(
                          results: state.searchResults,
                          stances: state.evidenceWithStance,
                          scrapingIndex: state.scrapingIndex,
                          scrapingTotal: state.scrapingTotal,
                          isScrapingPhase:
                              state.stage == PipelineStage.scraping,
                        ),
                      if (state.searchResults.isNotEmpty)
                        const SizedBox(height: 16),

                      // Stance chart (after stance detection)
                      if (state.verdict != null)
                        StanceChart(
                          supports: state.verdict!.supports,
                          refutes: state.verdict!.refutes,
                          neutral: state.verdict!.neutral,
                        ),
                      if (state.verdict != null) const SizedBox(height: 16),

                      // Verdict card
                      if (state.verdict != null)
                        VerdictCard(verdict: state.verdict!),
                      if (state.verdict != null) const SizedBox(height: 16),

                      // Error
                      if (state.hasError) _buildError(state.errorMessage),

                      const SizedBox(height: 40),
                    ]),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildExtractedClaims(VerifyState state) {
    return Container(
      decoration: NeoDeco.card(),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'ATOMIC CLAIMS',
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
                  state.claimType.toUpperCase(),
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: NeoColors.muted,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...state.extractedClaims.map(
            (c) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: NeoDeco.cardFlat(color: NeoColors.background),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      c.text,
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        color: NeoColors.charcoal,
                      ),
                    ),
                    if (c.entities.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: c.entities.map((e) {
                            return Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                border: Border.all(
                                  color: NeoColors.muted,
                                  width: 1,
                                ),
                              ),
                              child: Text(
                                e,
                                style: GoogleFonts.inter(
                                  fontSize: 11,
                                  color: NeoColors.muted,
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildError(String message) {
    return Container(
      decoration: BoxDecoration(
        color: NeoColors.fakeLight,
        border: Border.all(color: NeoColors.fake, width: 3),
        boxShadow: const [
          BoxShadow(color: NeoColors.fake, offset: Offset(4, 4), blurRadius: 0),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: NeoColors.fake),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: GoogleFonts.inter(fontSize: 14, color: NeoColors.charcoal),
            ),
          ),
        ],
      ),
    );
  }
}
