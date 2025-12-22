# Change: Add language selection and enforce consistent UI language

## Why
Messages currently mix Russian and English. For commercial use, the UI must be consistent per user and configurable.

## What Changes
- Default UI language to English.
- Add explicit language selection step during onboarding (right after /start).
- Add a settings option to change language later.
- Ensure all system messages use the stored language preference.

## Impact
- Affected specs: language (new)
- Affected code: onboarding/start handler, settings menu, user profile persistence, message routing
