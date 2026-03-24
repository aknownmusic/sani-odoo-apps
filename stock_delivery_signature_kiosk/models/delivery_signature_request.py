from odoo import fields, models


class StockDeliverySignatureRequest(models.Model):
    _name = "stock.delivery.signature.request"
    _description = "Tablet Delivery Signature Request"
    _order = "requested_at, id"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
    )
    picking_id = fields.Many2one(
        "stock.picking",
        required=True,
        index=True,
        ondelete="cascade",
    )
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("active", "Active"),
            ("done", "Done"),
            ("canceled", "Canceled"),
        ],
        required=True,
        default="queued",
        index=True,
    )
    requested_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    activated_at = fields.Datetime(copy=False)
    completed_at = fields.Datetime(copy=False)
    canceled_at = fields.Datetime(copy=False)
