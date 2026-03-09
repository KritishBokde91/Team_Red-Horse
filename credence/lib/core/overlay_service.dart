import 'package:flutter/services.dart';
import 'constants.dart';

/// Platform channel bridge for the Credence Shield (notification listener + overlay).
class OverlayService {
  static const _channel = MethodChannel('com.genzloop.credence/shield');

  /// Check if the shield is currently enabled.
  static Future<bool> isShieldEnabled() async {
    try {
      return await _channel.invokeMethod<bool>('isShieldEnabled') ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Enable or disable the shield.
  static Future<void> setShieldEnabled(bool enabled) async {
    await _channel.invokeMethod('setShieldEnabled', {'enabled': enabled});
    // Also set the API URL
    await _channel.invokeMethod('setApiUrl', {'url': AppConstants.apiBaseUrl});
  }

  /// Check if the app has overlay (draw over apps) permission.
  static Future<bool> hasOverlayPermission() async {
    try {
      return await _channel.invokeMethod<bool>('hasOverlayPermission') ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Request overlay permission (opens system settings).
  static Future<void> requestOverlayPermission() async {
    await _channel.invokeMethod('requestOverlayPermission');
  }

  /// Check if the app has notification listener access.
  static Future<bool> hasNotificationAccess() async {
    try {
      return await _channel.invokeMethod<bool>('hasNotificationAccess') ??
          false;
    } catch (_) {
      return false;
    }
  }

  /// Request notification listener access (opens system settings).
  static Future<void> requestNotificationAccess() async {
    await _channel.invokeMethod('requestNotificationAccess');
  }
}
