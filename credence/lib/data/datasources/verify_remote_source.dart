import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/sse_event_model.dart';
import '../../core/constants.dart';

/// Remote data source that opens an SSE connection to the /verify endpoint
/// and yields parsed [SseEvent] objects.
class VerifyRemoteSource {
  /// Streams SSE events from the backend /verify endpoint.
  Stream<SseEvent> verifyClaim(String claim) async* {
    final url = Uri.parse(
      '${AppConstants.apiBaseUrl}${AppConstants.verifyEndpoint}',
    );
    final request = http.Request('POST', url);
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.body = jsonEncode({'claim': claim});

    final client = http.Client();
    try {
      final response = await client.send(request);

      if (response.statusCode != 200) {
        yield SseEvent.fromJson({
          'type': 'error',
          'message': 'Server returned ${response.statusCode}',
        });
        return;
      }

      // Read byte stream → lines → parse SSE
      final lineStream = response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter());

      await for (final line in lineStream) {
        if (line.isEmpty) continue;

        // SSE format: "data: {...}" or "data: [DONE]"
        if (!line.startsWith('data: ')) continue;

        final payload = line.substring(6).trim();

        if (payload == '[DONE]') {
          yield const SseEvent(type: 'done', data: {'type': 'done'});
          break;
        }

        try {
          final json = jsonDecode(payload) as Map<String, dynamic>;
          yield SseEvent.fromJson(json);
        } catch (_) {
          // Skip malformed lines
        }
      }
    } catch (e) {
      yield SseEvent.fromJson({
        'type': 'error',
        'message': 'Connection failed: $e',
      });
    } finally {
      client.close();
    }
  }
}
