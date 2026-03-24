# Sani Odoo Apps

Dedicated repository for Odoo Apps Store modules.

## Structure

- Each published module must live in its own folder at the repository root.
- The branch name must match the Odoo series exactly, for example `19.0`.
- The first module scaffold in this repository is `sani_app`.

## Before Uploading To Odoo Apps

- Replace the placeholder support email in `sani_app/__manifest__.py`.
- Replace the placeholder icon and cover image in `sani_app/static/description/`.
- Update the English product description in `sani_app/static/description/index.html`.
- Add your actual module code, views, models, security rules, and tests.
- Push this repository to GitHub and register the SSH URL on Odoo Apps.

