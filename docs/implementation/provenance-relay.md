# Preserving source history

REQ-010. `SDK.mark` inspects input C2PA before changing pixels. Invalid/unreadable credentials abort export. A valid prior manifest is imported as a parent ingredient; altered material also carries its source as a parent. C2PA edit intent creates the required opening history before subsequent actions.

The integration suite verifies a signed image that is marked again as altered, then checks the resulting parent ingredient and active signature. This preserves history within this SDK workflow; it does not make arbitrary editors, CDNs or social platforms preserve provenance.

See [evidence](../validation/0.2.0a0.md).
