Create two SendGrid dynamic templates using the corresponding HTML files in this directory. Configure `TEMPLATE_ID_OWNERSHIP_TRANSFER_REQUEST_EMAIL` and `TEMPLATE_ID_OWNERSHIP_TRANSFER_RESULT_EMAIL` with their template IDs before enabling ownership requests. Suggested subjects: “Organization ownership request” and “Organization ownership request {{status}}”.

The request links to Invitations, which is available to every member. Dynamic fields are `organization`, `sender`, `recipient`, `expires_at`, `status`, and `open_platform_link`. SendGrid escapes these fields by default.

A missing template or a delivery failure is reported after saving the request or response; the saved action remains available in the application and must not be repeated. Result notices are stored independently of email delivery.
