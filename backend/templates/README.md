# Ownership transfer emails

Ownership transfer emails reuse the layout of the organization invite email. Create both templates as copies of the
live organization invite template (the one whose ID is in `TEMPLATE_ID_ORGANIZATION_INVITE_EMAIL`):

1. In SendGrid, open Email API → Dynamic Templates, find the organization invite template and click **Duplicate**.
   Do not edit the live invite template itself. If only "Duplicate version" is offered, do not use it, because it adds
   a version to the live invite template. Instead, create a new dynamic template, add a version in the code editor and
   paste the HTML of the invite template's active version.
2. In the copy, change only the subject, the heading, the body text and the button label as listed below. Keep the
   layout, the logo and the button link `{{open_platform_link}}` as they are.
3. Copy the ID of the new template (`d-…`) into the environment variable listed below on dev, staging and production.

Until a variable is set, the request or response is still saved, the email is not sent, and the owner sees a notice
that the email could not be delivered.

## Request to the new owner

- Environment variable: `TEMPLATE_ID_OWNERSHIP_TRANSFER_REQUEST_EMAIL`
- Template name: `Organization ownership transfer request`
- Fields: `invite_sender` (email of the current owner), `organization` (organization name), `open_platform_link`
  (`<APP_EMAIL_URL>/invitations`, opens the invitations panel). These are the same fields as in the invite email.
- Subject: `{{invite_sender}} wants to make you the owner of {{organization}}`
- Heading: `Become the owner of {{organization}}`
- Body:

  > {{invite_sender}} asked you to take over ownership of {{organization}} on LUML. As the owner you get full
  > control of the organization and its members, and the current owner becomes an admin. Nothing changes until you
  > accept. The request expires in 7 days.

- Button label: `Review request`

## Result for the previous owner

- Environment variable: `TEMPLATE_ID_OWNERSHIP_TRANSFER_RESULT_EMAIL`
- Template name: `Organization ownership transfer result`
- Fields: `organization` (organization name), `recipient` (email of the member who answered), `status` (`accepted`
  or `declined`), `open_platform_link` (`<APP_EMAIL_URL>/organization/<organization id>`, opens the organization).
- Subject: `{{recipient}} {{status}} ownership of {{organization}}`
- Heading: `Ownership transfer {{status}}`
- Body:

  > {{#equals status "accepted"}}{{recipient}} accepted your request and is now the owner of {{organization}}. You
  > stay in the organization as an admin.{{else}}{{recipient}} declined your request to transfer ownership of
  > {{organization}}. You are still the owner.{{/equals}}

- Button label: `Open organization`

A cancelled or expired request sends no email.
