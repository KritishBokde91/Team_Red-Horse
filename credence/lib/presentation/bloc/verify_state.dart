import 'package:equatable/equatable.dart';
import '../../data/models/evidence_model.dart';
import '../../data/models/verdict_model.dart';

/// Represents the pipeline stages in order.
enum PipelineStage {
  idle,
  claimExtraction,
  multiTierSearch,
  scraping,
  stanceDetection,
  verdict,
  explanation,
  completed,
  error,
}

/// Claim extracted from the input.
class ExtractedClaim {
  final String text;
  final List<String> entities;
  final String searchQuery;

  const ExtractedClaim({
    required this.text,
    required this.entities,
    required this.searchQuery,
  });
}

/// BLoC state for the verify feature.
class VerifyState extends Equatable {
  final PipelineStage stage;
  final String currentStageMessage;
  final String claim;

  // Stage 1: Extracted claims
  final List<ExtractedClaim> extractedClaims;
  final String claimType;

  // Stage 2: Search
  final int currentSearchTier;
  final String currentTierName;
  final List<EvidenceModel> searchResults;
  final Map<int, int> tierCounts; // tier -> result count

  // Stage 3: Scraping
  final int scrapingIndex;
  final int scrapingTotal;

  // Stage 4: Stance detection
  final List<EvidenceModel> evidenceWithStance;

  // Stage 5-6: Verdict + Explanation
  final VerdictModel? verdict;

  // Error
  final String errorMessage;

  const VerifyState({
    this.stage = PipelineStage.idle,
    this.currentStageMessage = '',
    this.claim = '',
    this.extractedClaims = const [],
    this.claimType = '',
    this.currentSearchTier = 0,
    this.currentTierName = '',
    this.searchResults = const [],
    this.tierCounts = const {},
    this.scrapingIndex = 0,
    this.scrapingTotal = 0,
    this.evidenceWithStance = const [],
    this.verdict,
    this.errorMessage = '',
  });

  bool get isIdle => stage == PipelineStage.idle;
  bool get isRunning =>
      stage != PipelineStage.idle &&
      stage != PipelineStage.completed &&
      stage != PipelineStage.error;
  bool get isCompleted => stage == PipelineStage.completed;
  bool get hasError => stage == PipelineStage.error;

  VerifyState copyWith({
    PipelineStage? stage,
    String? currentStageMessage,
    String? claim,
    List<ExtractedClaim>? extractedClaims,
    String? claimType,
    int? currentSearchTier,
    String? currentTierName,
    List<EvidenceModel>? searchResults,
    Map<int, int>? tierCounts,
    int? scrapingIndex,
    int? scrapingTotal,
    List<EvidenceModel>? evidenceWithStance,
    VerdictModel? verdict,
    String? errorMessage,
  }) {
    return VerifyState(
      stage: stage ?? this.stage,
      currentStageMessage: currentStageMessage ?? this.currentStageMessage,
      claim: claim ?? this.claim,
      extractedClaims: extractedClaims ?? this.extractedClaims,
      claimType: claimType ?? this.claimType,
      currentSearchTier: currentSearchTier ?? this.currentSearchTier,
      currentTierName: currentTierName ?? this.currentTierName,
      searchResults: searchResults ?? this.searchResults,
      tierCounts: tierCounts ?? this.tierCounts,
      scrapingIndex: scrapingIndex ?? this.scrapingIndex,
      scrapingTotal: scrapingTotal ?? this.scrapingTotal,
      evidenceWithStance: evidenceWithStance ?? this.evidenceWithStance,
      verdict: verdict ?? this.verdict,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }

  @override
  List<Object?> get props => [
    stage,
    currentStageMessage,
    claim,
    extractedClaims,
    claimType,
    currentSearchTier,
    searchResults.length,
    tierCounts,
    scrapingIndex,
    scrapingTotal,
    evidenceWithStance.length,
    verdict,
    errorMessage,
  ];
}
