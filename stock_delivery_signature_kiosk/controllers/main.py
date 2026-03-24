import json

from odoo.addons.web.controllers.utils import ensure_db
from odoo import _, SUPERUSER_ID, fields, http
from odoo.http import request
from odoo.service.common import exp_version
from odoo.tools import py_to_js_locale
from odoo.tools.image import image_data_uri


class StockDeliverySignatureKiosk(http.Controller):
    @staticmethod
    def _get_company(token):
        return request.env["res.company"].sudo().search(
            [("delivery_signature_kiosk_key", "=", token)],
            limit=1,
        )

    @staticmethod
    def _serialize_picking(picking):
        lines = []
        for move in picking.move_ids_without_package.filtered(
            lambda move: move.product_id and move.product_uom_qty
        ):
            lines.append(
                {
                    "id": move.id,
                    "product_name": move.product_id.display_name,
                    "qty": move.product_uom_qty,
                    "uom": move.product_uom.name,
                }
            )
        return {
            "id": picking.id,
            "name": picking.display_name,
            "partner_name": picking.partner_id.display_name or "",
            "origin": picking.origin or "",
            "scheduled_date": fields.Datetime.to_string(picking.scheduled_date)
            if picking.scheduled_date
            else "",
            "state": picking.state,
            "lines": lines,
        }

    @staticmethod
    def _get_pending_request(company):
        while True:
            queue_request = company._activate_next_delivery_signature_request()
            if not queue_request:
                return False

            picking = queue_request.picking_id.sudo()
            if not picking.exists():
                queue_request.write(
                    {
                        "state": "canceled",
                        "canceled_at": fields.Datetime.now(),
                    }
                )
                company._sync_delivery_signature_request_fields(False)
                continue

            if picking.company_id != company or picking.picking_type_code != "outgoing":
                queue_request.write(
                    {
                        "state": "canceled",
                        "canceled_at": fields.Datetime.now(),
                    }
                )
                company._sync_delivery_signature_request_fields(False)
                continue

            if picking.state == "cancel":
                queue_request.write(
                    {
                        "state": "canceled",
                        "canceled_at": fields.Datetime.now(),
                    }
                )
                company._sync_delivery_signature_request_fields(False)
                continue

            if picking.is_signed:
                queue_request.write(
                    {
                        "state": "done",
                        "completed_at": fields.Datetime.now(),
                    }
                )
                company._sync_delivery_signature_request_fields(False)
                continue

            return queue_request

    @http.route(
        ["/stock_delivery_signature/<token>"],
        type="http",
        auth="none",
        sitemap=False,
    )
    def open_kiosk_mode(self, token):
        ensure_db()
        company = self._get_company(token)
        if not company:
            return request.not_found()

        version_info = exp_version()
        return request.render(
            "stock_delivery_signature_kiosk.public_kiosk_mode",
            {
                "kiosk_backend_info": {
                    "token": token,
                    "company_id": company.id,
                    "company_name": company.name,
                    "lang": py_to_js_locale(company.partner_id.lang or company.env.lang),
                    "server_version_info": version_info.get("server_version_info"),
                }
            },
        )

    @http.route(
        "/stock_delivery_signature/pending",
        type="json",
        auth="none",
    )
    def get_pending_delivery(self, token):
        ensure_db()
        company = self._get_company(token)
        if not company:
            return {"status": "invalid"}

        queue_request = self._get_pending_request(company)
        if not queue_request:
            return {"status": "idle"}

        return {
            "status": "pending",
            "request": self._serialize_picking(queue_request.picking_id),
            "company_name": company.name,
            "company_logo": image_data_uri(company.logo) if company.logo else False,
        }

    @http.route(
        "/stock_delivery_signature/sign",
        type="json",
        auth="none",
    )
    def sign_delivery(self, token, picking_id, signature_image, signer_name=False):
        ensure_db()
        request.update_env(user=SUPERUSER_ID)
        company = self._get_company(token)
        if not company:
            return {"success": False, "error": _("Invalid kiosk URL.")}

        queue_request = self._get_pending_request(company)
        picking = request.env["stock.picking"].sudo().browse(int(picking_id)).exists()
        if not picking or not queue_request or picking != queue_request.picking_id:
            return {
                "success": False,
                "error": _(
                    "This delivery is no longer waiting for a signature on the tablet."
                ),
            }

        if not signature_image:
            return {"success": False, "error": _("Please draw a signature first.")}

        file_content = signature_image.split(",", 1)[-1]
        picking.write(
            {
                "signature": file_content,
                "tablet_signature_signed_at": fields.Datetime.now(),
                "tablet_signature_signed_name": signer_name or False,
            }
        )
        queue_request.write(
            {
                "state": "done",
                "completed_at": fields.Datetime.now(),
            }
        )
        company._sync_delivery_signature_request_fields(False)
        next_request = company._activate_next_delivery_signature_request()

        message = _("Signed via tablet kiosk.")
        if signer_name:
            message = _("Signed via tablet kiosk by %s.", signer_name)
        picking.message_post(body=message)

        return {
            "success": True,
            "picking_name": picking.display_name,
            "next_request": (
                self._serialize_picking(next_request.picking_id) if next_request else False
            ),
        }
