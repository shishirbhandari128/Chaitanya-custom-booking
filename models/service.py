from odoo import fields, models


class ChaitanyaAppointmentService(models.Model):
    _name = "chaitanya.appointment.service"
    _description = "Chaitanya Service"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "category_id, sequence, name"

    name = fields.Char(required=True, translate=True, tracking=True)
    sequence = fields.Integer(default=10)
    category_id = fields.Many2one(
        "chaitanya.appointment.service.category",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    
    short_description = fields.Char(translate=True)
    description = fields.Html(translate=True)
    benefits = fields.Html(translate=True)
    duration = fields.Integer(string="Duration (Minutes)", required=True, default=60)
    price = fields.Monetary(required=True, default=0.0)
    product_id = fields.Many2one("product.product", string="Checkout Product", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    image = fields.Binary(attachment=True)
    provider_ids = fields.Many2many(
        "chaitanya.appointment.provider",
        "chaitanya_appointment_provider_service_rel",
        "service_id",
        "provider_id",
        string="Therapists",
    )
    allow_gift = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean(default=True)
