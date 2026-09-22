## 1. Implementation
- [x] Add localized error message templates for write failures, timeouts, and invalid external responses.
- [x] Introduce/extend typed exceptions for Sheets write failures, network timeouts, and invalid external responses.
- [x] Map external client errors (Sheets/LLM/Whisper) to typed exceptions with clear user messages.
- [x] Update Telegram handlers to catch these exceptions, reply with the correct message, and reset session state.
- [x] Ensure success paths always send confirmation and error paths never hang.
- [x] Route user-derived Telegram output through safe chunked delivery.
- [x] Preserve progress and pending drafts when delivery or Sheets operations fail.
- [x] Register a global Telegram error handler with localized fallback feedback.
- [x] Suppress content-bearing third-party SDK debug logs.
- [x] Tag production images with Git SHA, reject dirty production deploys, and expose revision metadata.

## 2. Tests
- [x] Add unit tests for error mapping in Sheets/LLM/Whisper clients.
- [x] Add handler tests to verify user-facing errors and retained retry state on failure.
- [x] Add regression tests for long previews, retained retry state, logging privacy, and deploy provenance.
