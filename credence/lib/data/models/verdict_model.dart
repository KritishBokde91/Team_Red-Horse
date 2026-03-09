import 'package:equatable/equatable.dart';
import 'evidence_model.dart';

/// The final verdict payload from the API.
class VerdictModel extends Equatable {
  final String claim;
  final String verdict;
  final double veracityScore;
  final double confidence;
  final String explanation;
  final int supports;
  final int refutes;
  final int neutral;
  final List<EvidenceModel> evidence;

  const VerdictModel({
    required this.claim,
    required this.verdict,
    required this.veracityScore,
    required this.confidence,
    required this.explanation,
    required this.supports,
    required this.refutes,
    required this.neutral,
    required this.evidence,
  });

  factory VerdictModel.fromJson(Map<String, dynamic> json) {
    final summary = json['sources_summary'] as Map<String, dynamic>? ?? {};
    final evidenceList = (json['evidence'] as List<dynamic>? ?? [])
        .map((e) => EvidenceModel.fromVerdict(e as Map<String, dynamic>))
        .toList();

    return VerdictModel(
      claim: json['claim'] as String? ?? '',
      verdict: json['verdict'] as String? ?? 'UNVERIFIED',
      veracityScore: (json['veracity_score'] as num?)?.toDouble() ?? 0.0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      explanation: json['explanation'] as String? ?? '',
      supports: summary['supports'] as int? ?? 0,
      refutes: summary['refutes'] as int? ?? 0,
      neutral: summary['neutral'] as int? ?? 0,
      evidence: evidenceList,
    );
  }

  @override
  List<Object?> get props => [claim, verdict, veracityScore, confidence];
}
