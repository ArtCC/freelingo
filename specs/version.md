# Version

**1.5.5**

> Canonical project version. Update this file when bumping.
> Full history in [CHANGELOG.md](../CHANGELOG.md).

## Sync rule

When bumping the version, update these locations in sync:

| Location | What to update |
|----------|---------------|
| `specs/version.md` | Version number above |
| `CHANGELOG.md` | New `## [X.Y.Z]` section at top |
| `frontend/src/app/(app)/layout.tsx` | `vX.Y.Z` string in sidebar (desktop + mobile) |
| `frontend/src/components/whats-new/WhatsNew.tsx` | `WHATS_NEW_VERSION` constant |
| `messages/*.json` (all 10 locales) | Replace all `entry*` keys in the `whatsNew` namespace with the new version's entries; update the `version` key to match `WHATS_NEW_VERSION`. See `specs/whats-new.instructions.md` for the required structure. |

## What's New entries — mandatory prompt

**Before updating `WhatsNew.tsx` and the `whatsNew` namespace in any locale file, always ask the user:**

> "Do you want to update the What's New entries for this version, or just bump the version number?"

- If the user wants to update the entries: proceed to update `WHATS_NEW_VERSION`, all 10 locale files, and `WhatsNew.tsx`.
- If the user only wants to bump the number: update only `specs/version.md`, `CHANGELOG.md`, and `layout.tsx`. Leave `WhatsNew.tsx` and the `whatsNew` locale keys untouched.

Never update the What's New content silently — always wait for explicit confirmation.

## What's New entries — content guidelines

When the user confirms they want to update the entries, **do not write them immediately**. First:

1. Read the corresponding `## [X.Y.Z]` section in `CHANGELOG.md` to understand what changed.
2. Draft the entries in plain, friendly language aimed at end users — no technical jargon, no code references, no internal implementation details. Focus on what the user gains or experiences, not on how it was built.
3. Present the drafted entries to the user for review and wait for approval before writing anything to `WhatsNew.tsx` or any locale file.

**Tone guidelines:**
- Write as if explaining to a non-technical user who just wants to know what improved.
- Use short, positive sentences. Highlight the benefit, not the mechanism.
- Avoid terms like: base64, endpoint, migration, StaticFiles, VAD, barge-in, JWT, Redis, CEFR (spell it out if needed), alembic, router, component, namespace, i18n.
- Good example: "Your profile photo is now stored more efficiently — pages load faster and the app uses less database space."
- Bad example: "Avatar images are no longer encoded as base64 data URIs in the PostgreSQL users.avatar TEXT column."