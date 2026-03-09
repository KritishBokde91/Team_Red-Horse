import 'package:equatable/equatable.dart';

/// Represents a single evidence source with its stance analysis.
class EvidenceModel extends Equatable {
  final String url;
  final String title;
  final int tier;
  final String tierName;
  final double credibilityWeight;
  final String stance;
  final double stanceConfidence;
  final String stanceReasoning;
  final int chars;
  final bool scraped;
  final bool failed;

  const EvidenceModel({
    required this.url,
    required this.title,
    required this.tier,
    this.tierName = '',
    this.credibilityWeight = 0.5,
    this.stance = '',
    this.stanceConfidence = 0.0,
    this.stanceReasoning = '',
    this.chars = 0,
    this.scraped = false,
    this.failed = false,
  });

  factory EvidenceModel.fromSearchResult(Map<String, dynamic> json) {
    return EvidenceModel(
      url: json['url'] as String? ?? '',
      title: json['title'] as String? ?? '',
      tier: json['tier'] as int? ?? 0,
      tierName: json['tier_name'] as String? ?? '',
      credibilityWeight:
          (json['credibility_weight'] as num?)?.toDouble() ?? 0.5,
    );
  }

  factory EvidenceModel.fromVerdict(Map<String, dynamic> json) {
    return EvidenceModel(
      url: json['url'] as String? ?? '',
      title: json['title'] as String? ?? '',
      tier: json['tier'] as int? ?? 0,
      tierName: json['tier_name'] as String? ?? '',
      credibilityWeight:
          (json['credibility_weight'] as num?)?.toDouble() ?? 0.5,
      stance: json['stance'] as String? ?? '',
      stanceConfidence: (json['stance_confidence'] as num?)?.toDouble() ?? 0.0,
      stanceReasoning: json['stance_reasoning'] as String? ?? '',
      scraped: true,
    );
  }

  EvidenceModel copyWith({
    String? stance,
    double? stanceConfidence,
    String? stanceReasoning,
    int? chars,
    bool? scraped,
    bool? failed,
  }) {
    return EvidenceModel(
      url: url,
      title: title,
      tier: tier,
      tierName: tierName,
      credibilityWeight: credibilityWeight,
      stance: stance ?? this.stance,
      stanceConfidence: stanceConfidence ?? this.stanceConfidence,
      stanceReasoning: stanceReasoning ?? this.stanceReasoning,
      chars: chars ?? this.chars,
      scraped: scraped ?? this.scraped,
      failed: failed ?? this.failed,
    );
  }

  @override
  List<Object?> get props => [
    url,
    tier,
    stance,
    stanceConfidence,
    scraped,
    failed,
  ];
}
