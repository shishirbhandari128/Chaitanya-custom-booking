from odoo import fields, models, api
from datetime import timedelta


class ChaitanyaAppointmentProvider(models.Model):
    _name = "chaitanya.appointment.provider"
    _description = "Chaitanya Therapist"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one(
        "res.users",
        string="Odoo User",
        help="Used to show this therapist's bookings in Odoo Calendar/Appointments.",
    )
    resource_id = fields.Many2one(
        'appointment.resource',
        string='Appointment Resource',
        readonly=True,
        copy=False,
    )
    
    image = fields.Binary(attachment=True)
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
    last_auto_assigned = fields.Datetime(string="Last Auto Assigned", readonly=True)
    
    future_booking_count = fields.Integer(compute="_compute_booking_counts", store=True)
    today_booking_count = fields.Integer(compute="_compute_booking_counts", store=True)
    total_booking_count = fields.Integer(compute="_compute_booking_counts", store=True)



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('user_id'):
                user = self.env['res.users'].sudo().create({
                    'name': vals['name'],
                    'login': f"therapist.{vals['name'].lower().replace(' ', '.')}@chaitanya.com",
                    'groups_id': [(4, self.env.ref('base.group_user').id)],
                })
                vals['user_id'] = user.id

            resource = self.env['appointment.resource'].sudo().create({
                'name': vals['name'],
                'capacity': 1,
            })
            vals['resource_id'] = resource.id

        return super().create(vals_list)

    def write(self, vals):
        old_services = self.service_ids if 'service_ids' in vals else self.env['chaitanya.appointment.service']
        result = super().write(vals)

        if 'service_ids' in vals:
            affected_services = (old_services | self.service_ids).filtered('odoo_appointment_type_id')
            affected_services._sync_odoo_appointment_type()

        if 'active' in vals:
            self.service_ids.filtered('odoo_appointment_type_id')._sync_odoo_appointment_type()
            for provider in self:
                if provider.user_id:
                    provider.user_id.sudo().write({'active': vals['active']})
                if provider.resource_id:
                    provider.resource_id.sudo().write({'active': vals['active']})

        if 'name' in vals:
            for provider in self:
                if provider.resource_id:
                    provider.resource_id.sudo().write({'name': vals['name']})
                if provider.user_id:
                    provider.user_id.sudo().write({'name': vals['name']})

        return result

    def unlink(self):
        users = self.mapped('user_id').filtered(lambda u: u.active)
        resources = self.mapped('resource_id')
        result = super().unlink()
        resources.sudo().unlink()
        users.sudo().unlink()
        return result


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