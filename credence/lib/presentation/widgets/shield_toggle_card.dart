import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/overlay_service.dart';
import '../../core/theme.dart';

/// Neo-brutalism shield toggle card for enabling WhatsApp monitoring.
class ShieldToggleCard extends StatefulWidget {
  const ShieldToggleCard({super.key});

  @override
  State<ShieldToggleCard> createState() => _ShieldToggleCardState();
}

class _ShieldToggleCardState extends State<ShieldToggleCard> {
  bool _shieldEnabled = false;
  bool _hasOverlay = false;
  bool _hasNotifAccess = false;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadState();
  }

  Future<void> _loadState() async {
    final enabled = await OverlayService.isShieldEnabled();
    final overlay = await OverlayService.hasOverlayPermission();
    final notif = await OverlayService.hasNotificationAccess();
    if (mounted) {
      setState(() {
        _shieldEnabled = enabled;
        _hasOverlay = overlay;
        _hasNotifAccess = notif;
        _loading = false;
      });
    }
  }

  Future<void> _toggleShield(bool value) async {
    if (value) {
      // Check permissions first
      if (!_hasOverlay) {
        await OverlayService.requestOverlayPermission();
        await Future.delayed(const Duration(seconds: 1));
        await _loadState();
        return;
      }
      if (!_hasNotifAccess) {
        await OverlayService.requestNotificationAccess();
        await Future.delayed(const Duration(seconds: 1));
        await _loadState();
        return;
      }
    }

    await OverlayService.setShieldEnabled(value);
    setState(() => _shieldEnabled = value);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const SizedBox.shrink();

    return Container(
      decoration: BoxDecoration(
        color: _shieldEnabled ? NeoColors.charcoal : NeoColors.surface,
        border: Border.all(color: NeoColors.border, width: 3),
        boxShadow: const [
          BoxShadow(
            color: NeoColors.charcoal,
            offset: Offset(4, 4),
            blurRadius: 0,
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: _shieldEnabled
                      ? NeoColors.verified
                      : NeoColors.mutedLight,
                  border: Border.all(
                    color: _shieldEnabled
                        ? NeoColors.surface
                        : NeoColors.border,
                    width: 2,
                  ),
                ),
                child: Icon(
                  Icons.shield,
                  size: 18,
                  color: _shieldEnabled ? NeoColors.surface : NeoColors.muted,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'CREDENCE SHIELD',
                      style: GoogleFonts.spaceGrotesk(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: _shieldEnabled
                            ? NeoColors.surface
                            : NeoColors.charcoal,
                        letterSpacing: 2,
                      ),
                    ),
                    Text(
                      _shieldEnabled
                          ? 'Monitoring WhatsApp messages'
                          : 'Tap to enable fake news detection',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: _shieldEnabled
                            ? NeoColors.surface.withValues(alpha: 0.7)
                            : NeoColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
              GestureDetector(
                onTap: () => _toggleShield(!_shieldEnabled),
                child: Container(
                  width: 52,
                  height: 28,
                  decoration: BoxDecoration(
                    color: _shieldEnabled
                        ? NeoColors.verified
                        : NeoColors.mutedLight,
                    border: Border.all(
                      color: _shieldEnabled
                          ? NeoColors.surface
                          : NeoColors.border,
                      width: 2,
                    ),
                  ),
                  child: AnimatedAlign(
                    duration: const Duration(milliseconds: 200),
                    alignment: _shieldEnabled
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Container(
                      width: 22,
                      height: 22,
                      margin: const EdgeInsets.symmetric(horizontal: 1),
                      decoration: BoxDecoration(
                        color: _shieldEnabled
                            ? NeoColors.surface
                            : NeoColors.charcoal,
                        border: Border.all(color: NeoColors.border, width: 1),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),

          // Permission status
          if (!_hasOverlay || !_hasNotifAccess) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: NeoColors.unverifiedLight,
                border: Border.all(color: NeoColors.unverified, width: 1.5),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'PERMISSIONS NEEDED',
                    style: GoogleFonts.spaceGrotesk(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: NeoColors.unverified,
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 6),
                  _buildPermissionRow(
                    'Draw over apps',
                    _hasOverlay,
                    () => OverlayService.requestOverlayPermission(),
                  ),
                  const SizedBox(height: 4),
                  _buildPermissionRow(
                    'Notification access',
                    _hasNotifAccess,
                    () => OverlayService.requestNotificationAccess(),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPermissionRow(String label, bool granted, VoidCallback onTap) {
    return GestureDetector(
      onTap: granted ? null : onTap,
      child: Row(
        children: [
          Icon(
            granted ? Icons.check_circle : Icons.error_outline,
            size: 14,
            color: granted ? NeoColors.verified : NeoColors.fake,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              label,
              style: GoogleFonts.inter(fontSize: 12, color: NeoColors.charcoal),
            ),
          ),
          if (!granted)
            Text(
              'GRANT',
              style: GoogleFonts.spaceGrotesk(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: NeoColors.fake,
                letterSpacing: 1,
              ),
            ),
        ],
      ),
    );
  }
}
