import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

class AppConstants {
  AppConstants._();

  /// Backend base URL — switches for Android emulator vs web/desktop
  static String get apiBaseUrl {
    if (kIsWeb) return 'http://10.161.93.83:8080';
    try {
      if (Platform.isAndroid) return 'http://10.161.93.83:8080';
    } catch (_) {}
    return 'http://10.161.93.83:8080';
  }

  static const String verifyEndpoint = '/verify';
  static const String healthEndpoint = '/health';
}
