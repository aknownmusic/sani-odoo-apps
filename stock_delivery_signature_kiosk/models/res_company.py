import uuid

from werkzeug.urls import url_encode, url_join

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    delivery_signature_kiosk_key = fields.Char(
        default=lambda self: uuid.uuid4().hex,
        copy=False,
        groups="stock.group_stock_manager",
    )
    delivery_signature_kiosk_url = fields.Char(
        compute="_compute_delivery_signature_kiosk_url"
    )
    delivery_signature_pending_picking_id = fields.Many2one(
        "stock.picking",
        copy=False,
        groups="stock.group_stock_manager",
    )
    delivery_signature_request_ids = fields.One2many(
        "stock.delivery.signature.request",
        "company_id",
        groups="stock.group_stock_manager",
    )
    delivery_signature_requested_at = fields.Datetime(
        copy=False,
        groups="stock.group_stock_manager",
    )

    @api.depends("delivery_signature_kiosk_key")
    def _compute_delivery_signature_kiosk_url(self):
        base_url = self.env["res.company"].get_base_url()
        db_name = self.env.cr.dbname
        for company in self:
            target_path = f"/stock_delivery_signature/{company.delivery_signature_kiosk_key}"
            bootstrap_url = url_join(
                base_url,
                "/stock_delivery_signature_kiosk/static/src/bootstrap/kiosk_bootstrap.html",
            )
            company.delivery_signature_kiosk_url = f"{bootstrap_url}?{url_encode({'db': db_name, 'target': target_path})}"

    def _init_column(self, column_name):
        if column_name != "delivery_signature_kiosk_key":
            return super()._init_column(column_name)

        self.env.cr.execute(
            f"SELECT id FROM {self._table} WHERE delivery_signature_kiosk_key IS NULL"
        )
        company_rows = self.env.cr.dictfetchall()
        if not company_rows:
            return

        values_args = [(row["id"], uuid.uuid4().hex) for row in company_rows]
        query = f"""
            UPDATE {self._table}
               SET delivery_signature_kiosk_key = vals.token
              FROM (VALUES %s) AS vals(id, token)
             WHERE {self._table}.id = vals.id
        """
        self.env.cr.execute_values(query, values_args)

    def _regenerate_delivery_signature_kiosk_key(self):
        self.ensure_one()
        self.write({"delivery_signature_kiosk_key": uuid.uuid4().hex})

    def _sync_delivery_signature_request_fields(self, active_request=False):
        self.ensure_one()
        self.sudo().write(
            {
                "delivery_signature_pending_picking_id": (
                    active_request.picking_id.id if active_request else False
                ),
                "delivery_signature_requested_at": (
                    active_request.requested_at if active_request else False
                ),
            }
        )

    def _migrate_legacy_delivery_signature_request(self):
        self.ensure_one()
        Request = self.env["stock.delivery.signature.request"].sudo()
        open_request = Request.search(
            [
                ("company_id", "=", self.id),
                ("state", "in", ("queued", "active")),
            ],
            order="requested_at, id",
            limit=1,
        )
        if open_request or not self.delivery_signature_pending_picking_id:
            return
        request_time = self.delivery_signature_requested_at or fields.Datetime.now()
        legacy_request = Request.create(
            {
                "company_id": self.id,
                "picking_id": self.delivery_signature_pending_picking_id.id,
                "state": "active",
                "requested_at": request_time,
                "activated_at": request_time,
            }
        )
        self._sync_delivery_signature_request_fields(legacy_request)

    def _activate_next_delivery_signature_request(self):
        self.ensure_one()
        Request = self.env["stock.delivery.signature.request"].sudo()
        self._migrate_legacy_delivery_signature_request()
        active_request = Request.search(
            [
                ("company_id", "=", self.id),
                ("state", "=", "active"),
            ],
            order="requested_at, id",
            limit=1,
        )
        if active_request:
            self._sync_delivery_signature_request_fields(active_request)
            return active_request

        next_request = Request.search(
            [
                ("company_id", "=", self.id),
                ("state", "=", "queued"),
            ],
            order="requested_at, id",
            limit=1,
        )
        if not next_request:
            self._sync_delivery_signature_request_fields(False)
            return False

        next_request.write(
            {
                "state": "active",
                "activated_at": fields.Datetime.now(),
            }
        )
        self._sync_delivery_signature_request_fields(next_request)
        return next_request

    def _clear_delivery_signature_request(self):
        self.ensure_one()
        Request = self.env["stock.delivery.signature.request"].sudo()
        active_request = Request.search(
            [
                ("company_id", "=", self.id),
                ("state", "=", "active"),
            ],
            order="requested_at, id",
            limit=1,
        )
        if active_request:
            active_request.write(
                {
                    "state": "canceled",
                    "canceled_at": fields.Datetime.now(),
                }
            )
        self._sync_delivery_signature_request_fields(False)
        self._activate_next_delivery_signature_request()
