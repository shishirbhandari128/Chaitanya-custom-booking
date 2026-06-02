from odoo import fields, models, api
from datetime import timedelta


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
    weekly_template_ids = fields.One2many(
        "chaitanya.appointment.schedule.template",
        "provider_id",
        string="Weekly Schedule"
    )

   
    is_active_for_booking = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
    booking_ids = fields.One2many(
        "chaitanya.appointment.booking",
        "provider_id",
        string="Bookings"
    )
    future_booking_count = fields.Integer(compute="_compute_booking_counts", store=True)
    today_booking_count = fields.Integer(compute="_compute_booking_counts", store=True)
    total_booking_count = fields.Integer(compute="_compute_booking_counts", store=True)

 # override_ids = fields.One2many(
    #     "chaitanya.appointment.schedule.override",
    #     "provider_id",
    #     string="Schedule Overrides"
    # )




    @api.depends('booking_ids.state', 'booking_ids.start_datetime')
    def _compute_booking_counts(self):
        now = fields.Datetime.now()
        start_day = now.replace(hour=0, minute=0, second=0)
        tomorrow = fields.Datetime.to_datetime(fields.Date.today() + timedelta(days=1))

        for provider in self:
            bookings = provider.booking_ids.filtered(lambda b: b.state == "reserved")

            provider.total_booking_count = len(bookings)

            provider.today_booking_count = len(bookings.filtered(
                lambda b: start_day <= b.start_datetime < start_day + timedelta(days=1)
            ))

            provider.future_booking_count = len(bookings.filtered(
                lambda b: b.start_datetime >= tomorrow
            ))

    def action_view_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "All Bookings",
            "res_model": "chaitanya.appointment.booking",
            "view_mode": "list,form",
            "domain": [("provider_id", "=", self.id)],
        }

    def action_view_today_bookings(self):
        self.ensure_one()

        today = fields.Date.today()

        return {
            "type": "ir.actions.act_window",
            "name": "Today's Bookings",
            "res_model": "chaitanya.appointment.booking",
            "view_mode": "list,form",
            "domain": [
                ("provider_id", "=", self.id),
                ("start_datetime", ">=", str(today) + " 00:00:00"),
                ("start_datetime", "<", str(today) + " 23:59:59"),
            ],
    }

    def action_view_future_bookings(self):
        self.ensure_one()

        tomorrow = fields.Datetime.to_datetime(fields.Date.today() + timedelta(days=1))

        return {
            "type": "ir.actions.act_window",
            "name": "Future Bookings",
            "res_model": "chaitanya.appointment.booking",
            "view_mode": "list,form",
            "domain": [
                ("provider_id", "=", self.id),
                ("start_datetime", ">=", tomorrow),
            ],
        }