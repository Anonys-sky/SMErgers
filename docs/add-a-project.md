# Add your own test project

Use synthetic data only; this prototype is not intended for private client records.

1. Switch to **Project manager** or **Project director**. In Overview or Projects, find **Projects in progress** and select **Add project** (also available from Import chat). The form is at `/projects/new`.
2. Enter the project title, client, company, quote reference, event date and event type. Supply names for the project manager, project director and finance contact.
3. Add at least one original quote item: item name, positive quantity, unit and non-negative unit price in **RM**. Add or remove rows as needed. Optional comma-separated aliases help match chat wording; the item name is automatically included.
4. Optionally add a rate card for extras outside the original quote. These rates are not included in the starting quote total.
5. Either paste a WhatsApp text export **or** upload a UTF-8 `.txt` export without media—not both. The total request limit is **1,000,000 bytes**, including all form fields and upload overhead. Keep timestamps and sender names intact.
6. Select **Create project**. The project appears in **Projects in progress** and opens for review. Check detected changes against the chat, add missing prices, obtain director approval when required, and hand over to the client for confirmation. Finance can then view the draft bill and export CSV.

Android and iOS WhatsApp export formats are supported, with dates read **day/month/year**. For example:

```text
02/09/2026, 09:12 - Demo Client: Add 10 more guests
02/09/2026, 09:13 - Demo PM: OK noted
```

Use aliases such as `guests` on the corresponding quote item so the reader can match it.

## Validation and error handling

- Required fields and quote rows are checked on the server before creation. Quantities must be positive; original quote and rate-card prices must be non-negative. Numeric inputs in this form are capped at 1,000,000,000.
- Invalid dates or times in chat headers (including impossible dates and invalid AM/PM hours) show the offending line number. A failed submission creates no partial project and retains entered text; uploaded files must be selected again.
- Empty files, unrelated plain text and exports containing only system notices are rejected. A conversation with sender messages but no detected changes is still valid.
- The older **Import chat** flow at `/imports` continues to use an existing sample quote. It now rejects empty conversations before creating a record and handles malformed timestamps without crashing. Use **Add project** to enter a new quote; quote-document upload is not supported.
- Subsequent change-price entry and director discount decisions reject non-finite amounts such as `NaN`, `Infinity` and `1e309`, without changing the record or audit log. Zero amounts and negative credits remain valid.
- Individual change amounts are limited to **±RM1,000,000,000**, matching the intake price limit and preventing extreme finite prices from overflowing billing totals. Unusable extracted amounts remain unpriced for staff review.
- Quantity changes are checked against the original quote and confirmed changes at review, approval and confirmation. A cancellation cannot leave a negative quantity, even with a manually changed price or competing cancellations. Only confirmed additions can support a larger cancellation. Invalid quantities must be rejected and corrected at the source, not hidden by changing the price.
- Director discount decisions require a **zero or negative amount** and a written basis (for example, “5% of the original quote”). Positive amounts are rejected rather than silently converted into discounts.
- Client disputes queue the reason and affected item for the responsible person: the PM for ordinary changes, or the project director for discounts. Disputed changes remain excluded from billing until resolved and confirmed again. As with other prototype notifications, messages are queued in History, not delivered externally.
- Single-item and bulk action forms reject external return URLs, including protocol-relative and encoded bypasses. Safe local paths retain their query parameters and anchors; unsafe targets fall back to the project page.

**Storage limitation:** New and imported projects, approvals and quote versions are held in memory. Restarting the app or choosing **Reset demo data** removes them and restores the sample projects. Switching roles is a demo mechanism, not authentication.
