# React Dual-Draft Settings Dialog — Diff-Guard Pattern

## Problem

A settings dialog manages two independent draft values (e.g. data product + tool route).
It has a `hasChanged` guard that fires confirmation when either draft changed while
there are active messages. But only one `onUse` callback is diff-guarded:

```ts
// BAD — asymmetric: onUse fires unconditionally, onUse2 is diff-guarded
onUse(draft);
if (onUse2 && draft2 !== (selectedValue2 ?? '')) onUse2(draft2);
```

This is latent: currently safe only if `onUse`'s handler has an early-return on
`slug === selectedSlug`. Without that guard, a tool-route-only change triggers a
full data-product reset (new conversation ID + clearConversation()).

## Fix — symmetric diff-guards

```ts
if (draft !== selectedValue) onUse(draft);
if (onUse2 && draft2 !== (selectedValue2 ?? '')) onUse2(draft2);
```

Apply in BOTH `handleUse` (the no-confirmation path) and `handleConfirm` (the
confirmation path).

## Conditional confirmation copy

When `hasChanged` covers both drafts, the confirmation text must reflect which
draft(s) actually changed:

```tsx
{confirming && (
  <p className="settings-dialog__confirm-text">
    {draft !== selectedValue && draft2 !== (selectedValue2 ?? '')
      ? 'Switching data products and tool route will clear the current conversation. Continue?'
      : draft !== selectedValue
        ? 'Switching data products will clear the current conversation. Continue?'
        : 'Switching tool route will clear the current conversation. Continue?'}
  </p>
)}
```

## Rule of thumb

In any multi-draft dialog, every `onUseN` callback must use identical diff-guard
logic. If one is guarded, all must be. Asymmetry is always a latent bug.
