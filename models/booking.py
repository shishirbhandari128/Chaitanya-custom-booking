from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ChaitanyaAppointmentBooking(models.Model):
    _name = "chaitanya.appointment.booking"
    _description = "Chaitanya Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc"

    name = fields.Char(string="Booking Reference", default="/", readonly=True, copy=False)
    service_id = fields.Many2one(
        "chaitanya.appointment.service",
        required=False,
        ondelete="set null",
        tracking=True,
    )
    provider_id = fields.Many2one(
        "chaitanya.appointment.provider",
        string="Therapist",
        required=False,
        ondelete="set null",
        tracking=True,
    )
    therapist_id = fields.Many2one(
        "chaitanya.appointment.provider",
        string="Therapist",
        related="provider_id",
        store=True,
        readonly=False,
    )
    partner_id = fields.Many2one("res.partner", string="Customer")
    customer_name = fields.Char()
    customer_email = fields.Char()
    customer_phone = fields.Char()
    start_datetime = fields.Datetime(required=True, tracking=True)
    end_datetime = fields.Datetime(required=True, tracking=True)
    duration = fields.Integer(related="service_id.duration", store=True)
    booking_method = fields.Selection(
        [("therapist", "Book by Therapist"), ("availability", "Book by Availability")],
        required=True,
        default="availability",
    )
    is_gift = fields.Boolean()
    gift_delivery_type = fields.Selection([("online", "Online"), ("local", "Local Address")])
    gift_recipient_email = fields.Char()
    gift_recipient_address = fields.Text()
    gift_message = fields.Text()
    voucher_id = fields.Many2one("chaitanya.appointment.voucher")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    base_amount = fields.Monetary(default=0.0)
    discount_amount = fields.Monetary(default=0.0)
    final_amount = fields.Monetary(default=0.0)
    payment_method = fields.Selection(
        [("online", "Online Payment"), ("onsite", "Onsite Payment")],
        default="online",
        required=True,
    )
    payment_status = fields.Selection(
        [("unpaid", "Unpaid"), ("pending", "Pending"), ("paid", "Paid")],
        default="unpaid",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("reserved", "Reserved"),
            ("pending_payment", "Pending Payment"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
            ("completed", "Completed"),
            ("no_show", "No Show"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = sequence.next_by_code("chaitanya.appointment.booking") or "/"
            if vals.get("service_id") and vals.get("start_datetime") and not vals.get("end_datetime"):
                service = self.env["chaitanya.appointment.service"].browse(vals["service_id"])
                start_dt = fields.Datetime.from_string(vals["start_datetime"])
                vals["end_datetime"] = fields.Datetime.to_string(start_dt + timedelta(minutes=service.duration))
        return super().create(vals_list)

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetime_range(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime and booking.start_datetime >= booking.end_datetime:
                raise ValidationError("Booking end time must be after start time.")

    def action_confirm(self):
        for booking in self:
            if booking.service_id and booking.provider_id and booking.start_datetime:
                if not booking._is_slot_available(
                    booking.service_id,
                    booking.provider_id,
                    booking.start_datetime,
                    exclude_booking=booking,
                ):
                    raise UserError(_("The selected slot is no longer available."))
            booking.state = "confirmed"
            booking.payment_status = "pending" if booking.final_amount else "paid"
            if booking.payment_method == "onsite":
                booking.payment_status = "pending"
            if booking.voucher_id and booking.voucher_id.state == "active":
                booking.voucher_id.usage_count += 1
                if booking.voucher_id.usage_count >= booking.voucher_id.usage_limit:
                    booking.voucher_id.state = "used"

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_complete(self):
        self.write({"state": "completed"})

    def action_send_gift_voucher(self):
        for booking in self:
            if booking.is_gift:
                booking.message_post(body=_("Gift voucher marked for sending."))
        return True

    @api.model
    def _float_hour_to_datetime(self, slot_date, hour):
        whole_hours = int(hour)
        minutes = int(round((hour - whole_hours) * 60))
        return datetime.combine(slot_date, time(hour=whole_hours, minute=minutes))

    @api.model
    def _get_overlapping_booking_domain(self, provider, start_dt, end_dt, exclude_booking=False):
        domain = [
            ("provider_id", "=", provider.id),
            ("state", "in", ["reserved", "pending_payment", "confirmed"]),
            ("start_datetime", "<", end_dt),
            ("end_datetime", ">", start_dt),
        ]
        if exclude_booking:
            domain.append(("id", "!=", exclude_booking.id))
        return domain

    @api.model
    def _is_slot_available(self, service, provider, start_dt, exclude_booking=False):
        if not service or not provider or not start_dt:
            return False
        end_dt = start_dt + timedelta(minutes=service.duration)
        if provider not in service.provider_ids:
            return False

        availabilities = self.env["chaitanya.appointment.working_day"].sudo().search([
            ("provider_id", "=", provider.id),
            ("date", "=", fields.Date.to_date(start_dt)),
            ("active", "=", True),
        ])
        inside_availability = False
        for availability in availabilities:
            availability_start = self._float_hour_to_datetime(availability.date, availability.start_hour)
            availability_end = self._float_hour_to_datetime(availability.date, availability.end_hour)
            if availability_start <= start_dt and end_dt <= availability_end:
                inside_availability = True
                break
        if not inside_availability:
            return False

        overlap_count = self.sudo().search_count(
            self._get_overlapping_booking_domain(provider, start_dt, end_dt, exclude_booking)
        )
        return overlap_count == 0

    @api.model
    def get_available_slots(self, service_id, slot_date, provider_id=None):
        service = self.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        providers = service.provider_ids.filtered("active")
        if provider_id:
            providers = providers.filtered(lambda provider: provider.id == int(provider_id))
        slot_date = fields.Date.from_string(slot_date) if isinstance(slot_date, str) else slot_date
        slots = []
        seen = set()
        for provider in providers:
            availabilities = self.env["chaitanya.appointment.working_day"].sudo().search([
                ("provider_id", "=", provider.id),
                ("date", "=", slot_date),
                ("active", "=", True),
            ])
            for availability in availabilities:
                current = self._float_hour_to_datetime(slot_date, availability.start_hour)
                availability_end = self._float_hour_to_datetime(slot_date, availability.end_hour)
                while current + timedelta(minutes=service.duration) <= availability_end:
                    key = (provider.id, current)
                    if key not in seen and self._is_slot_available(service, provider, current):
                        seen.add(key)
                        slots.append({
                            "provider_id": provider.id,
                            "provider_name": provider.name,
                            "value": fields.Datetime.to_string(current),
                            "label": current.strftime("%I:%M %p"),
                        })
                    current += timedelta(minutes=availability.slot_interval)
        return slots

    @api.model
    def get_available_dates(self, service_id, provider_id):
        service = self.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        provider = self.env["chaitanya.appointment.provider"].sudo().browse(int(provider_id))
        if not service.exists() or not provider.exists() or provider not in service.provider_ids:
            return []
        dates = self.env["chaitanya.appointment.working_day"].sudo().search([
            ("provider_id", "=", provider.id),
            ("active", "=", True),
        ]).mapped("date")
        available_dates = []
        for slot_date in sorted(set(dates)):
            if self.get_available_slots(service.id, slot_date, provider.id):
                available_dates.append(fields.Date.to_string(slot_date))
        return available_dates

    @api.model
    def get_available_providers(self, service_id, start_datetime):
        service = self.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        start_dt = fields.Datetime.from_string(start_datetime)
        providers = service.provider_ids.filtered(
            lambda provider: self._is_slot_available(service, provider, start_dt)
        )
        return [{"id": provider.id, "name": provider.name} for provider in providers]

    @api.model
    def prepare_amounts(self, service, voucher=False, partner=False):
        base_amount = service.price
        discount_amount = voucher.compute_discount(base_amount) if voucher and voucher.is_valid_for_partner(partner) else 0.0
        return {
            "base_amount": base_amount,
            "discount_amount": discount_amount,
            "final_amount": max(base_amount - discount_amount, 0.0),
        }
