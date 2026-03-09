import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';

/// Neo-brutalism text input card with thick border and offset shadow.
class ClaimInputCard extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onSubmit;
  final bool isLoading;

  const ClaimInputCard({
    super.key,
    required this.controller,
    required this.onSubmit,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: NeoDeco.card(),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'VERIFY A CLAIM',
            style: GoogleFonts.spaceGrotesk(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: NeoColors.muted,
              letterSpacing: 2,
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            maxLines: 3,
            minLines: 1,
            style: GoogleFonts.inter(fontSize: 16, color: NeoColors.charcoal),
            decoration: const InputDecoration(
              hintText: 'Enter a claim to fact-check...',
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: isLoading ? null : onSubmit,
              child: isLoading
                  ? Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: NeoColors.surface,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Text('ANALYZING...'),
                      ],
                    )
                  : const Text('VERIFY'),
            ),
          ),
        ],
      ),
    );
  }
}
