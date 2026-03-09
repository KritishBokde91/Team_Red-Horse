import 'package:equatable/equatable.dart';

/// BLoC events for the verify feature.
abstract class VerifyEvent extends Equatable {
  const VerifyEvent();

  @override
  List<Object?> get props => [];
}

/// User submits a claim to verify.
class SubmitClaim extends VerifyEvent {
  final String claim;

  const SubmitClaim(this.claim);

  @override
  List<Object?> get props => [claim];
}

/// Reset the pipeline to initial state.
class ResetPipeline extends VerifyEvent {
  const ResetPipeline();
}
