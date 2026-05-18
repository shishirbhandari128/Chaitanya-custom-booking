from odoo import fields, models


class ChaitanyaAppointmentProvider(models.Model):
    _name = "chaitanya.appointment.provider"
    _description = "Chaitanya Therapist"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    image = fields.Binary(attachment=True)
    employee_id = fields.Many2one("res.users", string="Employee/User")
    user_id = fields.Many2one("res.users", string="Related User")
    specialization = fields.Char(translate=True)
    specialty_ids = fields.Many2many(
        "chaitanya.appointment.service.category",
        "ch_appt_provider_category_rel",
        "provider_id",
        "category_id",
        string="Specialties",
    )
    bio = fields.Html(translate=True)
    description = fields.Html(translate=True)
    service_ids = fields.Many2many(
        "chaitanya.appointment.service",
        "chaitanya_appointment_provider_service_rel",
        "provider_id",
        "service_id",
        string="Services",
    )
    available_slot_ids = fields.One2many(
        "chaitanya.appointment.working_day",
        "provider_id",
        string="Available Slots",
    )
    is_active_for_booking = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

