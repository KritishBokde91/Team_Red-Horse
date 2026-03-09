/// Typed wrapper for all SSE events from the /verify endpoint.
class SseEvent {
  final String type;
  final Map<String, dynamic> data;

  const SseEvent({required this.type, required this.data});

  factory SseEvent.fromJson(Map<String, dynamic> json) {
    return SseEvent(type: json['type'] as String? ?? 'unknown', data: json);
  }

  /// Convenience getters for common fields
  String get stage => data['stage'] as String? ?? '';
  String get message => data['message'] as String? ?? '';
  String get url => data['url'] as String? ?? '';
  String get title => data['title'] as String? ?? '';
  int get tier => data['tier'] as int? ?? 0;
  String get tierName => data['tier_name'] as String? ?? '';
  String get stance => data['stance'] as String? ?? '';
  double get weight => (data['weight'] as num?)?.toDouble() ?? 0.0;
  double get confidence => (data['confidence'] as num?)?.toDouble() ?? 0.0;
  int get count => data['count'] as int? ?? 0;
  int get index => data['index'] as int? ?? 0;
  int get total => data['total'] as int? ?? 0;
  int get chars => data['chars'] as int? ?? 0;
  int get totalResults => data['total_results'] as int? ?? 0;

  String get claimType => data['claim_type'] as String? ?? '';
  List<dynamic> get claims => data['claims'] as List<dynamic>? ?? [];
}
