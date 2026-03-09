import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/models/evidence_model.dart';
import '../../data/models/verdict_model.dart';
import '../../domain/usecases/verify_claim_usecase.dart';
import 'verify_event.dart';
import 'verify_state.dart';

/// BLoC that manages the fact-checking pipeline state.
///
/// Listens to the SSE stream and emits state updates for each event type,
/// giving the UI full visibility into every pipeline stage.
class VerifyBloc extends Bloc<VerifyEvent, VerifyState> {
  final VerifyClaimUseCase _verifyClaimUseCase;
  StreamSubscription<dynamic>? _streamSub;

  VerifyBloc(this._verifyClaimUseCase) : super(const VerifyState()) {
    on<SubmitClaim>(_onSubmitClaim);
    on<ResetPipeline>(_onReset);
  }

  Future<void> _onSubmitClaim(
    SubmitClaim event,
    Emitter<VerifyState> emit,
  ) async {
    await _streamSub?.cancel();

    emit(
      const VerifyState().copyWith(
        stage: PipelineStage.claimExtraction,
        claim: event.claim,
        currentStageMessage: 'Extracting atomic claims...',
      ),
    );

    final stream = _verifyClaimUseCase(event.claim);

    await for (final sseEvent in stream) {
      switch (sseEvent.type) {
        case 'stage':
          emit(_handleStage(sseEvent.stage, sseEvent.message));
          break;

        case 'claims_extracted':
          final claims = sseEvent.claims.map((c) {
            final m = c as Map<String, dynamic>;
            return ExtractedClaim(
              text: m['claim_text'] as String? ?? '',
              entities:
                  (m['entities'] as List<dynamic>?)
                      ?.map((e) => e.toString())
                      .toList() ??
                  [],
              searchQuery: m['search_query'] as String? ?? '',
            );
          }).toList();
          emit(
            state.copyWith(
              extractedClaims: claims,
              claimType: sseEvent.claimType,
            ),
          );
          break;

        case 'tier_searching':
          emit(
            state.copyWith(
              currentSearchTier: sseEvent.tier,
              currentTierName: sseEvent.tierName,
            ),
          );
          break;

        case 'tier_result':
          final result = EvidenceModel(
            url: sseEvent.url,
            title: sseEvent.title,
            tier: sseEvent.tier,
            credibilityWeight: sseEvent.weight,
          );
          emit(state.copyWith(searchResults: [...state.searchResults, result]));
          break;

        case 'tier_complete':
          final newCounts = Map<int, int>.from(state.tierCounts);
          newCounts[sseEvent.tier] = sseEvent.count;
          emit(state.copyWith(tierCounts: newCounts));
          break;

        case 'search_done':
          emit(
            state.copyWith(
              stage: PipelineStage.scraping,
              currentStageMessage:
                  'Scraping ${sseEvent.totalResults} evidence pages...',
            ),
          );
          break;

        case 'scraping_evidence':
          emit(
            state.copyWith(
              scrapingIndex: sseEvent.index,
              scrapingTotal: sseEvent.total,
            ),
          );
          break;

        case 'evidence_scraped':
          // Update existing search result with scraped info
          final updated = state.searchResults.map((r) {
            if (r.url == sseEvent.url) {
              return r.copyWith(scraped: true, chars: sseEvent.chars);
            }
            return r;
          }).toList();
          emit(state.copyWith(searchResults: updated));
          break;

        case 'evidence_failed':
          final updated = state.searchResults.map((r) {
            if (r.url == sseEvent.url) {
              return r.copyWith(failed: true);
            }
            return r;
          }).toList();
          emit(state.copyWith(searchResults: updated));
          break;

        case 'stance_result':
          final stanceEvidence = EvidenceModel(
            url: sseEvent.url,
            title: '',
            tier: sseEvent.tier,
            stance: sseEvent.stance,
            stanceConfidence: sseEvent.confidence,
            scraped: true,
          );
          emit(
            state.copyWith(
              evidenceWithStance: [...state.evidenceWithStance, stanceEvidence],
            ),
          );
          break;

        case 'verdict':
          final verdict = VerdictModel.fromJson(sseEvent.data);
          emit(
            state.copyWith(
              stage: PipelineStage.completed,
              verdict: verdict,
              currentStageMessage: 'Analysis complete',
            ),
          );
          break;

        case 'error':
          emit(
            state.copyWith(
              stage: PipelineStage.error,
              errorMessage: sseEvent.message,
            ),
          );
          break;

        case 'done':
          if (state.stage != PipelineStage.completed) {
            emit(state.copyWith(stage: PipelineStage.completed));
          }
          break;
      }
    }
  }

  VerifyState _handleStage(String stage, String message) {
    final pipelineStage = switch (stage) {
      'claim_extraction' => PipelineStage.claimExtraction,
      'multi_tier_search' => PipelineStage.multiTierSearch,
      'scraping' => PipelineStage.scraping,
      'stance_detection' => PipelineStage.stanceDetection,
      'verdict' => PipelineStage.verdict,
      'explanation' => PipelineStage.explanation,
      _ => state.stage,
    };
    return state.copyWith(stage: pipelineStage, currentStageMessage: message);
  }

  void _onReset(ResetPipeline event, Emitter<VerifyState> emit) {
    _streamSub?.cancel();
    emit(const VerifyState());
  }

  @override
  Future<void> close() {
    _streamSub?.cancel();
    return super.close();
  }
}
