## 1. Implementation
- [x] Add localized error message templates for write failures, timeouts, and invalid external responses.
- [x] Introduce/extend typed exceptions for Sheets write failures, network timeouts, and invalid external responses.
- [x] Map external client errors (Sheets/LLM/Whisper) to typed exceptions with clear user messages.
- [x] Update Telegram handlers to catch these exceptions, reply with the correct message, and reset session state.
- [x] Ensure success paths always send confirmation and error paths never hang.

## 2. Tests
- [ ] Add unit tests for error mapping in Sheets/LLM/Whisper clients.
- [ ] Add handler tests to verify user-facing errors and session reset on failure.
