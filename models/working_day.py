from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ChaitanyaAppointmentWorkingDay(models.Model):
    _name = "chaitanya.appointment.working_day"
    _description = "Therapist Availability"
    _order = "date, start_hour"

    name = fields.Char(compute="_compute_name", store=True)
    provider_id = fields.Many2one(
        "chaitanya.appointment.provider",
        string="Therapist",
        required=True,
        ondelete="cascade",
    )
    date = fields.Date(required=True, default=fields.Date.context_today)
    start = fields.Datetime(string="Start")
    end = fields.Datetime(string="End")
    stop = fields.Datetime(string="Stop")
    start_hour = fields.Float(required=True, default=10.0)
    end_hour = fields.Float(required=True, default=18.0)
    slot_interval = fields.Integer(string="Slot Interval (Minutes)", default=30, required=True)
    active = fields.Boolean(default=True)

    @api.depends("provider_id", "date", "start_hour", "end_hour")
    def _compute_name(self):
        for availability in self:
            provider = availability.provider_id.name or "Therapist"
            availability.name = "%s - %s (%s-%s)" % (
                provider,
                availability.date or "",
                availability.start_hour,
                availability.end_hour,
            )

    @api.constrains("start_hour", "end_hour", "slot_interval")
    def _check_time_range(self):
        for availability in self:
            if availability.start_hour < 0 or availability.end_hour > 24:
                raise ValidationError("Availability hours must be between 0 and 24.")
            if availability.start_hour >= availability.end_hour:
                raise ValidationError("End time must be after start time.")
            if availability.slot_interval <= 0:
                raise ValidationError("Slot interval must be greater than zero.")

