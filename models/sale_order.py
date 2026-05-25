from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    booking_id = fields.Many2one("chaitanya.appointment.booking", string="Booking", copy=False)

    chaitanya_service_id = fields.Many2one("chaitanya.appointment.service", copy=False)
    chaitanya_provider_id = fields.Many2one("chaitanya.appointment.provider", copy=False)
    chaitanya_start_datetime = fields.Datetime(copy=False)
    chaitanya_end_datetime = fields.Datetime(copy=False)

    chaitanya_booking_method = fields.Selection(
        [("therapist", "Book by Therapist"), ("availability", "Book by Availability")],
        copy=False,
    )

    chaitanya_is_gift = fields.Boolean(copy=False)
    chaitanya_gift_delivery_type = fields.Selection(
        [("online", "Online"), ("local", "Local Address")],
        copy=False,
    )
    chaitanya_gift_recipient_email = fields.Char(copy=False)
    chaitanya_gift_recipient_address = fields.Text(copy=False)
    chaitanya_gift_message = fields.Text(copy=False)

    chaitanya_voucher_id = fields.Many2one("chaitanya.appointment.voucher", copy=False)
    chaitanya_notes = fields.Text(copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_chaitanya_payment_method_name(self):
        self.ensure_one()

        transaction = self.transaction_ids.sorted("id")[-1:] if self.transaction_ids else False
        if transaction and transaction.provider_id:
            return transaction.provider_id.name

        if self.payment_term_id:
            return self.payment_term_id.name

        return "Unknown"

    def _get_chaitanya_payment_status(self):
        self.ensure_one()

        transaction = self.transaction_ids.sorted("id")[-1:] if self.transaction_ids else False
        if transaction and transaction.state == "done":
            return "paid"

        return "pending"

    def _create_chaitanya_bookings_from_order(self):
        Booking = self.env["chaitanya.appointment.booking"].sudo()

        for order in self:
            payment_method = order._get_chaitanya_payment_method_name()
            payment_status = order._get_chaitanya_payment_status()

            booking_lines = order.order_line.filtered(
                lambda line: line.chaitanya_service_id
                and line.chaitanya_provider_id
                and line.chaitanya_start_datetime
                and not line.booking_id
            )

            for line in booking_lines:
                service = line.chaitanya_service_id
                provider = line.chaitanya_provider_id
                start_dt = line.chaitanya_start_datetime

                if not Booking._is_slot_available(service, provider, start_dt):
                    raise UserError(
                        _("The selected appointment slot for %s is no longer available.")
                        % service.name
                    )

                amounts = Booking.prepare_amounts(
                    service,
                    line.chaitanya_voucher_id,
                    order.partner_id,
                )

                booking = Booking.create({
                    "service_id": service.id,
                    "provider_id": provider.id,
                    "partner_id": order.partner_id.id,
                    "customer_name": order.partner_id.name,
                    "customer_email": order.partner_id.email,
                    "customer_phone": order.partner_id.phone or order.partner_id.mobile,
                    "start_datetime": start_dt,
                    "end_datetime": line.chaitanya_end_datetime,
                    "booking_method": line.chaitanya_booking_method or "availability",
                    "is_gift": line.chaitanya_is_gift,
                    "gift_delivery_type": line.chaitanya_gift_delivery_type,
                    "gift_recipient_email": line.chaitanya_gift_recipient_email,
                    "gift_recipient_address": line.chaitanya_gift_recipient_address,
                    "gift_message": line.chaitanya_gift_message,
                    "voucher_id": line.chaitanya_voucher_id.id,
                    "payment_method": payment_method,
                    "payment_status": payment_status,
                    "state": "reserved",
                    "notes": line.chaitanya_notes,
                    "sale_order_id": order.id,
                    "sale_order_line_id": line.id,
                    **amounts,
                })

                line.booking_id = booking.id

        return True

    def action_confirm(self):
        res = super().action_confirm()
        self._create_chaitanya_bookings_from_order()
        return res




# from odoo import fields, models


# class ChaitanyaAppointmentBooking(models.Model):
#     _inherit = "chaitanya.appointment.booking"

#     sale_order_id = fields.Many2one("sale.order", readonly=True, copy=False)
#     sale_order_line_id = fields.Many2one("sale.order.line", readonly=True, copy=False)


# class SaleOrder(models.Model):
#     _inherit = "sale.order"

#     def action_confirm(self):
#         result = super().action_confirm()
#         for order in self:
#             linked_bookings = order.order_line.mapped("booking_id").filtered(
#                 lambda booking: booking.state in ("reserved", "pending_payment")
#             )
#             for booking in linked_bookings:
#                 partner = order.partner_id
#                 booking.write({
#                     "partner_id": partner.id,
#                     "customer_name": partner.name,
#                     "customer_email": partner.email,
#                     "customer_phone": partner.phone or partner.mobile,
#                 })
#                 booking.action_confirm()
#                 booking.payment_status = "paid"
#         return result

#     def _cart_find_product_line(self, product_id=None, line_id=None, **kwargs):
#         if kwargs.get("chaitanya_booking_id"):
#             return self.env["sale.order.line"]
#         return super()._cart_find_product_line(product_id=product_id, line_id=line_id, **kwargs)

#     def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
#         booking = self.env["chaitanya.appointment.booking"]
#         if line_id:
#             line = self.env["sale.order.line"].sudo().browse(line_id)
#             booking = line.booking_id
#         result = super()._cart_update(
#             product_id=product_id,
#             line_id=line_id,
#             add_qty=add_qty,
#             set_qty=set_qty,
#             **kwargs,
#         )
#         if booking:
#             line = booking.sale_order_line_id
#             if set_qty == 0 or not line.exists():
#                 booking.action_cancel()
#             elif line.product_uom_qty != 1:
#                 line.product_uom_qty = 1
#                 result["quantity"] = 1
#         return result

#     def _prepare_order_line_values(self, product_id, quantity, **kwargs):
#         values = super()._prepare_order_line_values(product_id, quantity, **kwargs)
#         booking_id = kwargs.get("chaitanya_booking_id")
#         if booking_id:
#             values["booking_id"] = booking_id
#         return values


# class SaleOrderLine(models.Model):
#     _inherit = "sale.order.line"

#     booking_id = fields.Many2one("chaitanya.appointment.booking", string="Booking", copy=False)
