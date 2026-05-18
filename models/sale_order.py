from odoo import fields, models


class ChaitanyaAppointmentBooking(models.Model):
    _inherit = "chaitanya.appointment.booking"

    sale_order_id = fields.Many2one("sale.order", readonly=True, copy=False)
    sale_order_line_id = fields.Many2one("sale.order.line", readonly=True, copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            linked_bookings = order.order_line.mapped("booking_id").filtered(
                lambda booking: booking.state in ("reserved", "pending_payment")
            )
            for booking in linked_bookings:
                partner = order.partner_id
                booking.write({
                    "partner_id": partner.id,
                    "customer_name": partner.name,
                    "customer_email": partner.email,
                    "customer_phone": partner.phone or partner.mobile,
                })
                booking.action_confirm()
                booking.payment_status = "paid"
        return result

    def _cart_find_product_line(self, product_id=None, line_id=None, **kwargs):
        if kwargs.get("chaitanya_booking_id"):
            return self.env["sale.order.line"]
        return super()._cart_find_product_line(product_id=product_id, line_id=line_id, **kwargs)

    def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
        booking = self.env["chaitanya.appointment.booking"]
        if line_id:
            line = self.env["sale.order.line"].sudo().browse(line_id)
            booking = line.booking_id
        result = super()._cart_update(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            **kwargs,
        )
        if booking:
            line = booking.sale_order_line_id
            if set_qty == 0 or not line.exists():
                booking.action_cancel()
            elif line.product_uom_qty != 1:
                line.product_uom_qty = 1
                result["quantity"] = 1
        return result

    def _prepare_order_line_values(self, product_id, quantity, **kwargs):
        values = super()._prepare_order_line_values(product_id, quantity, **kwargs)
        booking_id = kwargs.get("chaitanya_booking_id")
        if booking_id:
            values["booking_id"] = booking_id
        return values


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    booking_id = fields.Many2one("chaitanya.appointment.booking", string="Booking", copy=False)
