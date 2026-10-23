---
name: Financial safeguards
description: Rationale behind discount sign conventions, change-amount limits and cancellation checks.
---

Keep discounts explicitly signed reductions; reject positive discount inputs rather than automatically negating them. A zero decision is allowed when the director decides no reduction applies, but still requires its basis.

**Why:** Automatically correcting the sign could turn an accidental positive entry into an unintended financial concession. Zero preserves an explicit no-discount decision without inventing a charge.

**How to apply:** Preserve this contract in both the decision form and workflow validation.

Only confirmed additions may support a cancellation larger than the original quantity.

**Why:** Allowing an unconfirmed addition to support a removal makes the final quantity depend on whether that addition is later rejected. Recheck at confirmation because individually valid cancellations can compete for the same quantity.

**How to apply:** Keep the conservative confirmed-only calculation when extending editing, live ingestion or bulk actions.

The change-amount limit intentionally matches the existing intake limit.

**Why:** Finite-number checks alone do not prevent aggregate overflow; bounding individual inputs is appropriate for this small-business prototype and avoids accepting unrealistic amounts it cannot safely bill.

**How to apply:** Preserve a shared bound for staff-entered and extracted change prices; do not silently clamp invalid amounts into billable values.
