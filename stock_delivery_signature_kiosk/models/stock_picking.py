from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_tablet_signature_pending = fields.Boolean(
        compute="_compute_is_tablet_signature_pending"
    )
    tablet_signature_signed_at = fields.Datetime(copy=False)
    tablet_signature_signed_name = fields.Char(copy=False)

    def _get_open_tablet_signature_requests(self):
        return self.env["stock.delivery.signature.request"].sudo().search(
            [
                ("picking_id", "in", self.ids),
                ("state", "in", ("queued", "active")),
            ]
        )

    @api.depends("company_id.delivery_signature_pending_picking_id", "company_id.delivery_signature_request_ids.state")
    def _compute_is_tablet_signature_pending(self):
        requests_by_picking = {
            request.picking_id.id: request
            for request in self._get_open_tablet_signature_requests()
        }
        for picking in self:
            picking.is_tablet_signature_pending = picking.id in requests_by_picking

    def _check_can_use_tablet_signature(self):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Save this transfer before sending it to the tablet."))
        if self.picking_type_code != "outgoing":
            raise UserError(
                _("Tablet signing is only available for outgoing deliveries.")
            )
        if self.state == "cancel":
            raise UserError(_("Canceled transfers cannot be sent to the tablet."))
        if self.is_signed:
            raise UserError(_("This delivery has already been signed."))

    def _get_tablet_signature_request(self):
        self.ensure_one()
        return self.env["stock.delivery.signature.request"].sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("picking_id", "=", self.id),
                ("state", "in", ("queued", "active")),
            ],
            order="requested_at, id",
            limit=1,
        )

    def action_request_tablet_signature(self):
        self.ensure_one()
        self._check_can_use_tablet_signature()

        company = self.company_id.sudo()
        company._migrate_legacy_delivery_signature_request()

        existing_request = self._get_tablet_signature_request()
        if existing_request:
            if existing_request.state == "active":
                message = _(
                    "The tablet kiosk is already waiting for a signature for %s.",
                    self.display_name,
                )
            else:
                message = _(
                    "The signature request for %s is already queued for the tablet.",
                    self.display_name,
                )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Tablet request already exists"),
                    "message": message,
                    "type": "warning",
                    "sticky": False,
                },
            }

        request_vals = {
            "company_id": company.id,
            "picking_id": self.id,
            "requested_at": fields.Datetime.now(),
        }
        queue_request = self.env["stock.delivery.signature.request"].sudo().create(
            request_vals
        )
        active_request = company._activate_next_delivery_signature_request()

        if active_request == queue_request:
            title = _("Tablet signature requested")
            message = _(
                "The tablet kiosk is now waiting for a signature for %s.",
                self.display_name,
            )
            notification_type = "success"
        else:
            title = _("Tablet signature queued")
            message = _(
                "%s has been added to the tablet queue and will appear after the current signature is completed.",
                self.display_name,
            )
            notification_type = "info"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }

    def action_cancel_tablet_signature_request(self):
        self.ensure_one()
        company = self.company_id.sudo()
        company._migrate_legacy_delivery_signature_request()
        queue_request = self._get_tablet_signature_request()
        if not queue_request:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No tablet request found"),
                    "message": _(
                        "There is no open tablet signature request for %s.",
                        self.display_name,
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }

        was_active = queue_request.state == "active"
        queue_request.write(
            {
                "state": "canceled",
                "canceled_at": fields.Datetime.now(),
            }
        )

        if was_active:
            company._sync_delivery_signature_request_fields(False)
            company._activate_next_delivery_signature_request()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Tablet signature canceled"),
                "message": _(
                    "The tablet kiosk request for %s has been cleared.",
                    self.display_name,
                ),
                "type": "warning",
                "sticky": False,
            },
        }
