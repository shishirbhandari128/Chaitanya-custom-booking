from odoo import api, fields, models
from odoo.exceptions import ValidationError



class ChaitanyaScheduleTemplate(models.Model):
    _name = "chaitanya.appointment.schedule.template"
    _description = "Therapist Schedule Template"

    provider_id = fields.Many2one(
        "chaitanya.appointment.provider",
        required=True,
        ondelete="cascade"
    )

    active = fields.Boolean(default=True)

    date_ids = fields.One2many(
        "chaitanya.appointment.schedule.date",
        "template_id",
        string="Schedule Dates"
    )




class ChaitanyaScheduleDate(models.Model):
    _name = "chaitanya.appointment.schedule.date"
    _description = "Therapist Schedule Date"

    template_id = fields.Many2one(
        "chaitanya.appointment.schedule.template",
        required=True,
        ondelete="cascade"
    )

    date = fields.Date(required=True)

    slot_ids = fields.One2many(
        "chaitanya.appointment.schedule.slot",
        "date_id",
        string="Time Slots"
    )


class ChaitanyaScheduleSlot(models.Model):
    _name = "chaitanya.appointment.schedule.slot"
    _description = "Therapist Time Slots"
    _order = "start_hour"

    date_id = fields.Many2one(
        "chaitanya.appointment.schedule.date",
        required=True,
        ondelete="cascade"
    )

    start_hour = fields.Float(required=True)
    end_hour = fields.Float(required=True)
    is_off = fields.Boolean(default=False)


    slot_interval = fields.Integer(default=30)

    @api.constrains("start_hour", "end_hour")
    def _check_valid_time(self):
        for rec in self:
            if rec.start_hour >= rec.end_hour:
                raise ValidationError(
                    "Start time must be before end time."
                )

