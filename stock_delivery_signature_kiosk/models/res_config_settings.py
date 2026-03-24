from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    delivery_signature_kiosk_url = fields.Char(
        related="company_id.delivery_signature_kiosk_url"
    )

    def regenerate_delivery_signature_kiosk_key(self):
        for settings in self:
            settings.company_id._regenerate_delivery_signature_kiosk_key()
