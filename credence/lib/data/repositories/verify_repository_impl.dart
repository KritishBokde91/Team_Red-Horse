import '../../domain/repositories/verify_repository.dart';
import '../datasources/verify_remote_source.dart';
import '../models/sse_event_model.dart';

/// Concrete implementation that delegates to [VerifyRemoteSource].
class VerifyRepositoryImpl implements VerifyRepository {
  final VerifyRemoteSource _remoteSource;

  VerifyRepositoryImpl({VerifyRemoteSource? remoteSource})
    : _remoteSource = remoteSource ?? VerifyRemoteSource();

  @override
  Stream<SseEvent> verifyClaim(String claim) {
    return _remoteSource.verifyClaim(claim);
  }
}
