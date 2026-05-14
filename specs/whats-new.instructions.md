---
description: "What's New modal specification for FreeLingo: version-aware changelog overlay shown once per version on the dashboard, following the same pattern as OnboardingTour."
applyTo: "frontend/src/**"
---

# What's New modal

## Objective

Show users a brief summary of what changed in the current version every time a new version is deployed. The modal appears automatically on the dashboard on the user's first visit after an update, then never again until the next version is released. No backend involvement — entirely client-side using localStorage, mirroring the OnboardingTour pattern.

---

## Behaviour

| Scenario | Result |
|----------|--------|
| User visits dashboard and has never seen the current version's modal | Modal appears automatically |
| User dismisses the modal (button or backdrop click) | `localStorage` key set; modal never appears again for this version |
| New version is deployed | Storage key changes → modal reappears for all users on next dashboard visit |
| User logs out | Storage key is **not** cleared (unlike the tour) — no need to show it again on re-login within the same version |

The key difference from OnboardingTour: the tour clears on logout (new users must see it); the What's New modal does not — a returning user who already saw v1.5.0 notes should not see them again after logging out and back in.

---

## localStorage key

```
fl_whats_new_seen_<version>
```

Example for v1.5.0:

```
fl_whats_new_seen_v1.5.0
```

The version string is defined as a constant inside the component:

```ts
const WHATS_NEW_VERSION = 'v1.5.0'
const STORAGE_KEY = `fl_whats_new_seen_${WHATS_NEW_VERSION}`
```

To ship a new release: update `WHATS_NEW_VERSION` and add the new entries to the translation files.

---

## Component

**File:** `frontend/src/components/whats-new/WhatsNew.tsx`

`'use client'` component. Rendered unconditionally in `dashboard/page.tsx` immediately after `<OnboardingTour />`. Returns `null` when not visible — zero DOM output.

### Priority with OnboardingTour

Both components are rendered in the DOM at the same time. The tour takes visual priority: if `fl_tour_done` is absent (new user), the tour is visible and the What's New modal should not compete. The What's New component must check for the tour key and skip rendering if the tour is active:

```ts
useEffect(() => {
  const tourDone = localStorage.getItem('fl_tour_done')
  const seen = localStorage.getItem(STORAGE_KEY)
  if (tourDone && !seen) {
    setVisible(true)
  }
}, [])
```

This ensures:
- New user → sees tour only
- Returning user on new version → sees What's New only
- Returning user on same version → sees neither

---

## Modal structure

Single-panel layout — no step pagination. All entries for the version are shown in one scrollable list.

```
┌─────────────────────────────────────────┐
│  ✦  WHAT'S NEW — v1.5.0                │
├─────────────────────────────────────────┤
│                                         │
│  ◎  FEATURE LABEL                       │
│     Short description of the feature.  │
│                                         │
│  ▣  ANOTHER FEATURE                     │
│     Short description.                  │
│                                         │
│  △  IMPROVEMENT                         │
│     Short description.                  │
│                                         │
├─────────────────────────────────────────┤
│                        [ Got it → ]     │
└─────────────────────────────────────────┘
```

### Layout details

- **Backdrop**: full-screen fixed overlay (`z-50`), semi-transparent with `backdrop-blur-sm`. Clicking it dismisses the modal.
- **Modal card**: centered, `max-w-md`, same border/surface tokens as the tour (`border-fl-border bg-fl-surface`).
- **Header**: version label (`✦ WHAT'S NEW — vX.Y.Z`) in `font-mono tracking-widest uppercase text-fl-muted-2`.
- **Entry list**: each entry has an icon (`◎ ▣ △ ◇ ✦ ▣` cycling), a label in `uppercase text-fl-muted-2`, and a description in `text-fl-muted-1`.
- **Divider** between header, list, and footer using `border-fl-border`.
- **Footer**: single `Got it →` button (filled `bg-fl-accent`) right-aligned.
- **Max height**: `max-h-[50vh] overflow-y-auto` on the entries container to handle long lists gracefully.

---

## Translations

Namespace: `whatsNew` in all `messages/*.json` files.

**Rule: all 10 locale files must always be updated in sync.** The supported locales are: `en`, `es`, `de`, `fr`, `it`, `nl`, `pl`, `pt`, `ro`, `ru`. No locale may be left behind or contain entries from a previous version.

Structure for each version's entries:

```json
"whatsNew": {
  "title": "What's New",
  "version": "v1.4.15",
  "cta": "Got it",
  "entry1": {
    "label": "Feature label",
    "desc": "Short description of the feature or improvement."
  },
  "entry2": {
    "label": "Another feature",
    "desc": "Short description."
  }
}
```

The number of entries is variable per version. The component reads entries dynamically using `useMessages()` from `next-intl` — it inspects the raw `whatsNew` namespace object and filters keys matching `/^entry\d+$/`, sorted numerically. **Do not use `useTranslations` in a try/catch loop to detect missing keys** — `next-intl` does not throw on missing keys; it returns the key path as a string, which would cause an infinite loop.

**When shipping a new version: replace all existing `entry*` keys with the new version's entries.** Do not accumulate old entries — only the current version's changelog items should be present. The `version` key must also be updated to match `WHATS_NEW_VERSION` in the component.

---

## Files to create / modify

| File | Action |
|------|--------|
| `frontend/src/components/whats-new/WhatsNew.tsx` | Create — the modal component |
| `frontend/src/app/(app)/dashboard/page.tsx` | Modify — import and render `<WhatsNew />` after `<OnboardingTour />` |
| `messages/en.json` (and all locale files) | Modify — add `whatsNew` namespace with current version entries |

---

## Maintenance workflow (per release)

1. Bump `WHATS_NEW_VERSION` constant in `WhatsNew.tsx` to the new version string.
2. **Replace** (not append) all `entry*` keys in the `whatsNew` namespace across **all 10 locale files** (`en`, `es`, `de`, `fr`, `it`, `nl`, `pl`, `pt`, `ro`, `ru`) with the new version's changelog items. Also update the `version` key.
3. Remove any `entry*` keys from the previous version that are no longer needed — the `whatsNew` namespace must only contain entries relevant to the current version.
4. Deploy. All existing users will see the modal on their next dashboard visit.

No database migration, no backend change, no API endpoint needed.