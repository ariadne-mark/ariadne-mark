# Visible disclosure

REQ-009 remains in progress as a legal-mapping requirement. `--visible` bakes an AI-generated/AI-altered label into an image or every video frame before watermarking and signing. The API equivalent is `SDK.mark(..., visible=True)`.

This is a technical component, not a decision that a label is required for every scenario. The application must determine applicability and provide accessible disclosures at the appropriate point in its own UI. See [regulatory mapping](../compliance/release-mapping.md).
