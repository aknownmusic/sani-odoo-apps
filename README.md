# Sani Odoo Apps

Dedicated repository for Odoo Apps Store modules.

## Active Module

This branch currently targets Odoo `18.0` and contains:

- `stock_delivery_signature_kiosk`

## What The Module Does

`stock_delivery_signature_kiosk` lets warehouse staff send an outgoing delivery to a tablet-friendly kiosk page where the customer can review the transfer lines and sign directly on the device.

## Structure

- Each published module lives in its own folder at the repository root.
- The branch name matches the Odoo series exactly, for example `17.0`, `18.0`, or `19.0`.
- Store assets for a module belong in `static/description/`.

## Before Uploading To Odoo Apps

- Replace the placeholder icon and cover image in `stock_delivery_signature_kiosk/static/description/` if you want branded visuals.
- Review the English product description in `stock_delivery_signature_kiosk/static/description/index.html`.
- Set your final support contact in the module manifest if needed.
- Test the module on an Odoo 18 database before submitting.
