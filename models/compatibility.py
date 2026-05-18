from odoo import fields, models


class ChaitanyaTherapistCompatibility(models.Model):
    _name = "chaitanya.therapist"
    _description = "Legacy Chaitanya Therapist Compatibility"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True)
    image = fields.Binary(attachment=True)
    employee_id = fields.Many2one("res.users", string="Employee/User")
    user_id = fields.Many2one("res.users", string="Related User")
    specialization = fields.Char()
    specialty_ids = fields.Many2many(
        "chaitanya.appointment.service.category",
        "ch_therapist_category_rel",
        "therapist_id",
        "category_id",
        string="Specialties",
    )
    bio = fields.Html()
    description = fields.Html()
    service_ids = fields.Many2many(
        "chaitanya.appointment.service",
        "ch_therapist_service_rel",
        "therapist_id",
        "service_id",
        string="Services",
    )
    available_slot_ids = fields.One2many("chaitanya.therapist.availability", "therapist_id", string="Available Slots")
    is_active_for_booking = fields.Boolean(default=True)
    active = fields.Boolean(default=True)


class ChaitanyaTherapistAvailabilityCompatibility(models.Model):
    _name = "chaitanya.therapist.availability"
    _description = "Legacy Therapist Availability Compatibility"
    _order = "date, start_hour"

    name = fields.Char()
    therapist_id = fields.Many2one("chaitanya.therapist", ondelete="cascade")
    date = fields.Date(default=fields.Date.context_today)
    start = fields.Datetime()
    end = fields.Datetime()
    stop = fields.Datetime()
    start_hour = fields.Float(default=10.0)
    end_hour = fields.Float(default=18.0)
    slot_interval = fields.Integer(default=30)
    active = fields.Boolean(default=True)
