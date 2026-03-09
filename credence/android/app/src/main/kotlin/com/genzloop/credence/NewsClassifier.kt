package com.genzloop.credence

/**
 * NewsClassifier — Lightweight on-device heuristic to determine
 * if a WhatsApp message is a news claim or regular chat.
 *
 * This saves ~95% of API calls by filtering out "hi", "ok", emojis,
 * stickers, and other non-news messages BEFORE hitting the backend.
 */
object NewsClassifier {

    // Minimum message length to consider as potential news
    private const val MIN_NEWS_LENGTH = 40

    // News-related keywords (English + Hindi romanized)
    private val NEWS_KEYWORDS = setOf(
        // Politics
        "government", "minister", "prime minister", "president", "election",
        "voted", "parliament", "BJP", "congress", "AAP", "modi", "rahul",
        "opposition", "bill passed", "supreme court", "high court",
        "sarkar", "mantri", "chunav", "pradhan",

        // Crime & Disaster
        "arrested", "killed", "murdered", "bomb", "blast", "attack",
        "earthquake", "flood", "cyclone", "tsunami", "landslide",
        "accident", "crash", "fire broke", "explosion",
        "giraftar", "hatya", "hadsa",

        // Health
        "virus", "vaccine", "covid", "pandemic", "WHO", "ICMR",
        "hospital", "outbreak", "disease", "cancer cure",
        "dawai", "bimari",

        // Misinformation indicators
        "breaking", "urgent", "shocking", "share this", "forward",
        "don't ignore", "must watch", "confirmed", "exposed",
        "leaked", "banned", "secret", "they don't want you to know",
        "100% true", "verified", "fact check",
        "jaroor padhe", "share karo", "sach",

        // Economy & Finance
        "RBI", "stock market", "sensex", "rupee", "demonetization",
        "tax", "GST", "inflation", "recession", "bank",

        // Sports
        "world cup", "olympics", "cricket", "match fixed",
        "champion", "winner", "trophy", "IPL", "FIFA",

        // International
        "war", "invasion", "nuclear", "sanctions", "NATO",
        "UN", "ceasefire", "border", "troops",

        // Media
        "report", "according to", "sources say", "official statement",
        "press conference", "media", "newspaper", "channel",
    )

    // Patterns that indicate this is NOT news (skip immediately)
    private val SKIP_PATTERNS = listOf(
        "^[\\p{So}\\p{Sc}\\s]+$",           // Emoji-only messages
        "^(ok|okay|yes|no|hi|hello|hey|bye|gm|gn|good morning|good night|hmm|haha|lol|😂|👍|🙏|❤️|thanks|thank you|sure|done|coming|wait|where|when|how much|kya|haan|nahi|theek|accha|sahi|bol|bata|chal|aaja|kab|kahan|kitna)$",
    )

    private val skipRegexes = SKIP_PATTERNS.map { Regex(it, RegexOption.IGNORE_CASE) }

    /**
     * Classify whether a message is likely news or just regular chat.
     *
     * @return ClassificationResult with isNews flag and confidence
     */
    fun classify(message: String): ClassificationResult {
        val trimmed = message.trim()

        // Too short to be news
        if (trimmed.length < MIN_NEWS_LENGTH) {
            return ClassificationResult(false, 0.0, "Message too short")
        }

        // Skip patterns (emoji-only, common chat words)
        for (regex in skipRegexes) {
            if (regex.matches(trimmed)) {
                return ClassificationResult(false, 0.0, "Common chat pattern")
            }
        }

        // Check for news keywords
        val lowerMessage = trimmed.lowercase()
        val matchedKeywords = NEWS_KEYWORDS.filter { keyword ->
            lowerMessage.contains(keyword.lowercase())
        }

        if (matchedKeywords.isEmpty()) {
            return ClassificationResult(false, 0.1, "No news keywords found")
        }

        // Calculate confidence based on keyword density
        val confidence = when {
            matchedKeywords.size >= 4 -> 0.95
            matchedKeywords.size >= 3 -> 0.85
            matchedKeywords.size >= 2 -> 0.70
            else -> 0.50
        }

        // Extra boost for forwarded message indicators
        val isForwarded = lowerMessage.contains("forwarded") ||
                lowerMessage.contains("forward") ||
                lowerMessage.contains("share")

        val finalConfidence = if (isForwarded) {
            minOf(confidence + 0.15, 1.0)
        } else {
            confidence
        }

        return ClassificationResult(
            isNews = true,
            confidence = finalConfidence,
            reason = "Matched: ${matchedKeywords.take(3).joinToString(", ")}"
        )
    }

    data class ClassificationResult(
        val isNews: Boolean,
        val confidence: Double,
        val reason: String,
    )
}
