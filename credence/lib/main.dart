import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'core/theme.dart';
import 'data/datasources/verify_remote_source.dart';
import 'data/repositories/verify_repository_impl.dart';
import 'domain/usecases/verify_claim_usecase.dart';
import 'presentation/bloc/verify_bloc.dart';
import 'presentation/screens/verify_screen.dart';

void main() {
  runApp(const CredenceApp());
}

class CredenceApp extends StatelessWidget {
  const CredenceApp({super.key});

  @override
  Widget build(BuildContext context) {
    // Wire up clean architecture dependency chain
    final remoteSource = VerifyRemoteSource();
    final repository = VerifyRepositoryImpl(remoteSource: remoteSource);
    final useCase = VerifyClaimUseCase(repository);

    return BlocProvider(
      create: (_) => VerifyBloc(useCase),
      child: MaterialApp(
        title: 'Credence',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        home: const VerifyScreen(),
      ),
    );
  }
}
