import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Neo-Brutalism palette — minimal, professional, bold.
class NeoColors {
  NeoColors._();

  // Base
  static const Color background = Color(0xFFFAFAF9);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color charcoal = Color(0xFF1C1917);
  static const Color border = Color(0xFF1C1917);

  // Muted
  static const Color muted = Color(0xFF78716C);
  static const Color mutedLight = Color(0xFFE7E5E4);

  // Accent — used sparingly
  static const Color fake = Color(0xFFEF4444);
  static const Color fakeLight = Color(0xFFFEE2E2);
  static const Color verified = Color(0xFF22C55E);
  static const Color verifiedLight = Color(0xFFDCFCE7);
  static const Color unverified = Color(0xFFF59E0B);
  static const Color unverifiedLight = Color(0xFFFEF3C7);

  // Tiers
  static const Color tier1 = Color(0xFF3B82F6);
  static const Color tier2 = Color(0xFF8B5CF6);
  static const Color tier3 = Color(0xFF64748B);
}

/// Neo-Brutalism decoration helpers
class NeoDeco {
  NeoDeco._();

  static BoxDecoration card({Color? color}) => BoxDecoration(
    color: color ?? NeoColors.surface,
    border: Border.all(color: NeoColors.border, width: 3),
    boxShadow: const [
      BoxShadow(color: NeoColors.charcoal, offset: Offset(4, 4), blurRadius: 0),
    ],
  );

  static BoxDecoration cardFlat({Color? color}) => BoxDecoration(
    color: color ?? NeoColors.surface,
    border: Border.all(color: NeoColors.border, width: 2),
  );

  static BoxDecoration pill({Color? color}) => BoxDecoration(
    color: color ?? NeoColors.surface,
    border: Border.all(color: NeoColors.border, width: 2),
    borderRadius: BorderRadius.circular(100),
  );
}

/// App theme
ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: NeoColors.background,
    colorScheme: const ColorScheme.light(
      primary: NeoColors.charcoal,
      onPrimary: NeoColors.surface,
      surface: NeoColors.surface,
      onSurface: NeoColors.charcoal,
    ),
    textTheme: GoogleFonts.spaceGroteskTextTheme().copyWith(
      headlineLarge: GoogleFonts.spaceGrotesk(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        color: NeoColors.charcoal,
      ),
      headlineMedium: GoogleFonts.spaceGrotesk(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        color: NeoColors.charcoal,
      ),
      titleLarge: GoogleFonts.spaceGrotesk(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        color: NeoColors.charcoal,
      ),
      titleMedium: GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: NeoColors.charcoal,
      ),
      bodyLarge: GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        color: NeoColors.charcoal,
      ),
      bodyMedium: GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: NeoColors.muted,
      ),
      labelLarge: GoogleFonts.spaceGrotesk(
        fontSize: 14,
        fontWeight: FontWeight.w700,
        color: NeoColors.charcoal,
      ),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: NeoColors.background,
      elevation: 0,
      titleTextStyle: GoogleFonts.spaceGrotesk(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: NeoColors.charcoal,
      ),
      iconTheme: const IconThemeData(color: NeoColors.charcoal),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: NeoColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.zero,
        borderSide: const BorderSide(color: NeoColors.border, width: 3),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.zero,
        borderSide: const BorderSide(color: NeoColors.border, width: 3),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.zero,
        borderSide: const BorderSide(color: NeoColors.charcoal, width: 3),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      hintStyle: GoogleFonts.inter(color: NeoColors.muted, fontSize: 15),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: NeoColors.charcoal,
        foregroundColor: NeoColors.surface,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
        textStyle: GoogleFonts.spaceGrotesk(
          fontSize: 16,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
  );
}
