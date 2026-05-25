from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ChaitanyaAppointmentBooking(models.Model):
    _name = "chaitanya.appointment.booking"
    _description = "Chaitanya Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc"

    name = fields.Char(string="Booking Reference", default="/", readonly=True, copy=False)

    service_id = fields.Many2one("chaitanya.appointment.service", ondelete="set null", tracking=True)
    provider_id = fields.Many2one("chaitanya.appointment.provider", string="Therapist", ondelete="set null", tracking=True)
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

    sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True, copy=False)
    sale_order_line_id = fields.Many2one("sale.order.line", string="Sale Order Line", readonly=True, copy=False)

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

    payment_method = fields.Char(string="Payment Method")
    payment_status = fields.Selection(
        [("unpaid", "Unpaid"), ("pending", "Pending"), ("paid", "Paid")],
        default="unpaid",
        required=True,
    )

    state = fields.Selection(
        [("reserved", "Reserved"), ("cancelled", "Cancelled")],
        default="reserved",
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
                vals["end_datetime"] = fields.Datetime.to_string(
                    start_dt + timedelta(minutes=service.duration)
                )

        return super().create(vals_list)

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetime_range(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime and booking.start_datetime >= booking.end_datetime:
                raise ValidationError(_("Booking end time must be after start time."))

    def action_cancel(self):
        self.write({"state": "cancelled"})

    @api.model
    def _get_overlapping_booking_domain(self, provider, start_dt, end_dt, exclude_booking=False):
        domain = [
            ("provider_id", "=", provider.id),
            ("start_datetime", "<", end_dt),
            ("end_datetime", ">", start_dt),
            ("state", "=", "reserved"),
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

        overlap_count = self.sudo().search_count(
            self._get_overlapping_booking_domain(provider, start_dt, end_dt, exclude_booking)
        )

        return overlap_count == 0

    @api.model
    def prepare_amounts(self, service, voucher=False, partner=False):
        base_amount = service.price
        discount_amount = (
            voucher.compute_discount(base_amount)
            if voucher and voucher.is_valid_for_partner(partner)
            else 0.0
        )

        return {
            "base_amount": base_amount,
            "discount_amount": discount_amount,
            "final_amount": max(base_amount - discount_amount, 0.0),
        }


# from datetime import datetime, time, timedelta

# from odoo import _, api, fields, models
# from odoo.exceptions import UserError, ValidationError


# class ChaitanyaAppointmentBooking(models.Model):
#     _name = "chaitanya.appointment.booking"
#     _description = "Chaitanya Booking"
#     _inherit = ["mail.thread", "mail.activity.mixin"]
#     _order = "start_datetime desc"

#     RESERVATION_MINUTES = 1

#     name = fields.Char(string="Booking Reference", default="/", readonly=True, copy=False)
#     service_id = fields.Many2one(
#         "chaitanya.appointment.service",
#         required=False,
#         ondelete="set null",
#         tracking=True,
#     )
#     provider_id = fields.Many2one(
#         "chaitanya.appointment.provider",
#         string="Therapist",
#         required=False,
#         ondelete="set null",
#         tracking=True,
#     )
#     therapist_id = fields.Many2one(
#         "chaitanya.appointment.provider",
#         string="Therapist",
#         related="provider_id",
#         store=True,
#         readonly=False,
#     )
#     partner_id = fields.Many2one("res.partner", string="Customer")
#     customer_name = fields.Char()
#     customer_email = fields.Char()
#     customer_phone = fields.Char()

#     start_datetime = fields.Datetime(required=True, tracking=True)
#     end_datetime = fields.Datetime(required=True, tracking=True)
#     duration = fields.Integer(related="service_id.duration", store=True)

#     reserved_until = fields.Datetime(string="Reserved Until", index=True)

#     sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True, copy=False)
#     sale_order_line_id = fields.Many2one("sale.order.line", string="Sale Order Line", readonly=True, copy=False)

#     booking_method = fields.Selection(
#         [("therapist", "Book by Therapist"), ("availability", "Book by Availability")],
#         required=True,
#         default="availability",
#     )

#     is_gift = fields.Boolean()
#     gift_delivery_type = fields.Selection([("online", "Online"), ("local", "Local Address")])
#     gift_recipient_email = fields.Char()
#     gift_recipient_address = fields.Text()
#     gift_message = fields.Text()

#     voucher_id = fields.Many2one("chaitanya.appointment.voucher")

#     currency_id = fields.Many2one(
#         "res.currency",
#         default=lambda self: self.env.company.currency_id,
#         required=True,
#     )
#     base_amount = fields.Monetary(default=0.0)
#     discount_amount = fields.Monetary(default=0.0)
#     final_amount = fields.Monetary(default=0.0)

#     payment_method = fields.Selection(
#         [("online", "Online Payment"), ("onsite", "Onsite Payment")],
#         default="online",
#         required=True,
#     )
#     payment_status = fields.Selection(
#         [("unpaid", "Unpaid"), ("pending", "Pending"), ("paid", "Paid")],
#         default="unpaid",
#         required=True,
#     )

#     state = fields.Selection(
#         [
#             ("draft", "Draft"),
#             ("reserved", "Reserved"),
#             ("pending_payment", "Pending Payment"),
#             ("confirmed", "Confirmed"),
#             ("cancelled", "Cancelled"),
#             ("completed", "Completed"),
#             ("no_show", "No Show"),
#         ],
#         default="draft",
#         required=True,
#         tracking=True,
#     )

#     notes = fields.Text()

#     @api.model_create_multi
#     def create(self, vals_list):
#         sequence = self.env["ir.sequence"]
#         now = fields.Datetime.now()

#         for vals in vals_list:
#             if vals.get("name", "/") == "/":
#                 vals["name"] = sequence.next_by_code("chaitanya.appointment.booking") or "/"

#             if vals.get("service_id") and vals.get("start_datetime") and not vals.get("end_datetime"):
#                 service = self.env["chaitanya.appointment.service"].browse(vals["service_id"])
#                 start_dt = fields.Datetime.from_string(vals["start_datetime"])
#                 vals["end_datetime"] = fields.Datetime.to_string(
#                     start_dt + timedelta(minutes=service.duration)
#                 )

#             if vals.get("state") == "reserved" and not vals.get("reserved_until"):
#                 vals["reserved_until"] = fields.Datetime.to_string(
#                     now + timedelta(minutes=self.RESERVATION_MINUTES)
#                 )

#         return super().create(vals_list)

#     def write(self, vals):
#         if vals.get("state") == "reserved" and "reserved_until" not in vals:
#             vals["reserved_until"] = fields.Datetime.to_string(
#                 fields.Datetime.now() + timedelta(minutes=self.RESERVATION_MINUTES)
#             )
#         return super().write(vals)

#     @api.constrains("start_datetime", "end_datetime")
#     def _check_datetime_range(self):
#         for booking in self:
#             if booking.start_datetime and booking.end_datetime and booking.start_datetime >= booking.end_datetime:
#                 raise ValidationError("Booking end time must be after start time.")

#     def action_confirm(self):
#         for booking in self:
#             if booking.service_id and booking.provider_id and booking.start_datetime:
#                 if not booking._is_slot_available(
#                     booking.service_id,
#                     booking.provider_id,
#                     booking.start_datetime,
#                     exclude_booking=booking,
#                 ):
#                     raise UserError(_("The selected slot is no longer available."))

#             booking.write({
#                 "state": "confirmed",
#                 "reserved_until": False,
#                 "payment_status": "pending" if booking.final_amount else "paid",
#             })

#             if booking.payment_method == "onsite":
#                 booking.payment_status = "pending"

#             if booking.voucher_id and booking.voucher_id.state == "active":
#                 booking.voucher_id.usage_count += 1
#                 if booking.voucher_id.usage_count >= booking.voucher_id.usage_limit:
#                     booking.voucher_id.state = "used"

#     def action_cancel(self):
#         self.write({
#             "state": "cancelled",
#             "reserved_until": False,
#         })

#     def action_complete(self):
#         self.write({"state": "completed"})

#     def action_send_gift_voucher(self):
#         for booking in self:
#             if booking.is_gift:
#                 booking.message_post(body=_("Gift voucher marked for sending."))
#         return True

#     @api.model
#     def _get_overlapping_booking_domain(self, provider, start_dt, end_dt, exclude_booking=False):
#         now = fields.Datetime.now()

#         domain = [
#             ("provider_id", "=", provider.id),
#             ("start_datetime", "<", end_dt),
#             ("end_datetime", ">", start_dt),
#             "|",
#                 ("state", "in", ["pending_payment", "confirmed"]),
#                 "&",
#                     ("state", "=", "reserved"),
#                     ("reserved_until", ">", now),
#         ]

#         if exclude_booking:
#             domain.append(("id", "!=", exclude_booking.id))

#         return domain

#     @api.model
#     def _is_slot_available(self, service, provider, start_dt, exclude_booking=False):
#         if not service or not provider or not start_dt:
#             return False

#         end_dt = start_dt + timedelta(minutes=service.duration)

#         if provider not in service.provider_ids:
#             return False

#         overlap_count = self.sudo().search_count(
#             self._get_overlapping_booking_domain(
#                 provider,
#                 start_dt,
#                 end_dt,
#                 exclude_booking,
#             )
#         )

#         return overlap_count == 0

#     @api.model
#     def _cron_cancel_expired_reservations(self):
#         now = fields.Datetime.now()

#         expired_bookings = self.sudo().search([
#             ("state", "=", "reserved"),
#             ("payment_status", "in", ["pending", "unpaid"]),
#             ("reserved_until", "!=", False),
#             ("reserved_until", "<=", now),
#         ])

#         for booking in expired_bookings:
#             line = booking.sale_order_line_id
#             order = booking.sale_order_id

#             booking.action_cancel()

#             if line and line.exists() and order and order.state in ("draft", "sent"):
#                 line.sudo().unlink()
#         return True

#     @api.model
#     def prepare_amounts(self, service, voucher=False, partner=False):
#         base_amount = service.price
#         discount_amount = (
#             voucher.compute_discount(base_amount)
#             if voucher and voucher.is_valid_for_partner(partner)
#             else 0.0
#         )

#         return {
#             "base_amount": base_amount,
#             "discount_amount": discount_amount,
#             "final_amount": max(base_amount - discount_amount, 0.0),
#         }