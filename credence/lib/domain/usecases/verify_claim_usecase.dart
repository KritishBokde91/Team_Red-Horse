import '../../data/models/sse_event_model.dart';
import '../repositories/verify_repository.dart';

/// Use case that orchestrates the fact-checking pipeline streaming.
class VerifyClaimUseCase {
  final VerifyRepository _repository;

  VerifyClaimUseCase(this._repository);

  /// Returns a stream of SSE events for the given claim.
  Stream<SseEvent> call(String claim) {
    return _repository.verifyClaim(claim);
  }
}
