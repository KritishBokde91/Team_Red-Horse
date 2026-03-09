import '../../data/models/sse_event_model.dart';

/// Abstract repository for claim verification.
abstract class VerifyRepository {
  /// Streams SSE events from the backend for a given claim.
  Stream<SseEvent> verifyClaim(String claim);
}
