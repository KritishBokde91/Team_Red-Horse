import 'package:flutter_test/flutter_test.dart';
import 'package:credence/main.dart';

void main() {
  testWidgets('Credence app smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const CredenceApp());
    expect(find.text('CREDENCE'), findsOneWidget);
    expect(find.text('VERIFY'), findsOneWidget);
  });
}
