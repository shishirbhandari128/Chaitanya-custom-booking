from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    booking_id = fields.Many2one("chaitanya.appointment.booking", string="Booking", copy=False)

    chaitanya_service_id = fields.Many2one("chaitanya.appointment.service", copy=False)
    chaitanya_duration = fields.Integer(string="Booking Duration (Minutes)", copy=False)
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

    def _get_chaitanya_booking_line_amounts(self, booking_lines):
        self.ensure_one()
        currency = self.currency_id

        positive_lines = self.order_line.filtered(
            lambda line: not line.display_type
            and line.price_subtotal > 0
            and not getattr(line, "is_delivery", False)
        )

        reward_lines = self.order_line.filtered(
            lambda line: not line.display_type
            and line.price_subtotal < 0
        )

        total_reward_discount = abs(sum(reward_lines.mapped("price_subtotal")))
        positive_subtotal = sum(positive_lines.mapped("price_subtotal"))

        amounts_by_line = {}

        for line in booking_lines:
            base_amount = currency.round(line.price_unit * line.product_uom_qty)

            direct_discount = currency.round(
                max(base_amount - line.price_subtotal, 0.0)
            )

            allocated_reward_discount = 0.0
            if total_reward_discount and positive_subtotal:
                allocated_reward_discount = currency.round(
                    total_reward_discount * (line.price_subtotal / positive_subtotal)
                )

            discount_amount = currency.round(
                direct_discount + allocated_reward_discount
            )

            final_amount = currency.round(
                max(base_amount - discount_amount, 0.0)
            )

            amounts_by_line[line.id] = {
                "base_amount": base_amount,
                "discount_amount": discount_amount,
                "final_amount": final_amount,
            }

        return amounts_by_line

    def _create_chaitanya_bookings_from_order(self):
        Booking = self.env["chaitanya.appointment.booking"].sudo()

        for order in self:
            order._chaitanya_validate_booking_lines()
            payment_method = order._get_chaitanya_payment_method_name()
            payment_status = order._get_chaitanya_payment_status()

            booking_lines = order.order_line.filtered(
                lambda line: line.chaitanya_service_id
                and line.chaitanya_provider_id
                and line.chaitanya_start_datetime
                and not line.booking_id
            )

            amounts_by_line = order._get_chaitanya_booking_line_amounts(booking_lines)

            for line in booking_lines:
                service = line.chaitanya_service_id
                provider = line.chaitanya_provider_id
                start_dt = line.chaitanya_start_datetime

                if not Booking._is_slot_available(service, provider, start_dt):
                    raise UserError(
                        _("The selected appointment slot for %s is no longer available.")
                        % service.name
                    )

                amounts = amounts_by_line.get(line.id, {
                    "base_amount": line.price_unit * line.product_uom_qty,
                    "discount_amount": 0.0,
                    "final_amount": line.price_subtotal,
                })

                booking = Booking.create({
                    "service_id": service.id,
                    "product_id": line.product_id.id,
                    "product_variant_description": line.product_id.display_name,
                    "provider_id": provider.id,
                    "partner_id": order.partner_id.id,
                    "customer_name": order.partner_id.name,
                    "customer_email": order.partner_id.email,
                    "customer_phone": order.partner_id.phone or order.partner_id.mobile,
                    "start_datetime": start_dt,
                    "end_datetime": line.chaitanya_end_datetime,
                    "duration": line.chaitanya_duration,    
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
    
    
   

    

    def _chaitanya_get_invalid_booking_lines(self):
        self.ensure_one()

        Booking = self.env["chaitanya.appointment.booking"].sudo()
        invalid_lines = []

        booking_lines = self.order_line.sudo().filtered(
            lambda line: line.chaitanya_service_id
            or line.chaitanya_provider_id
            or line.chaitanya_start_datetime
        )

        for line in booking_lines:
            service = line.chaitanya_service_id.sudo()
            provider = line.chaitanya_provider_id.sudo()
            start_dt = line.chaitanya_start_datetime

            reason = False

            if not service or not service.exists():
                reason = _("The selected service no longer exists.")

            elif not service.active or not service.website_published:
                reason = _("The selected service is no longer available.")

            elif not provider or not provider.exists():
                reason = _("The selected therapist no longer exists.")

            elif not provider.active or not provider.is_active_for_booking:
                reason = _("The selected therapist is no longer available for booking.")

            elif provider not in service.provider_ids.sudo():
                reason = _("The selected therapist is no longer assigned to this service.")

            elif not start_dt:
                reason = _("The booking time is missing.")

            elif not Booking._is_slot_available(
                service,
                provider,
                start_dt,
                exclude_booking=line.booking_id.sudo() if line.booking_id else False,
            ):
                reason = _("The selected time slot is no longer available.")

            if reason:
                invalid_lines.append({
                    "line": line,
                    "reason": reason,
                })

        return invalid_lines


    def _chaitanya_invalid_booking_message(self):
        self.ensure_one()

        invalid_lines = self._chaitanya_get_invalid_booking_lines()

        if not invalid_lines:
            return ""

        message_lines = [_("Some booking items in your cart are no longer available:")]

        for item in invalid_lines:
            line = item["line"].sudo()
            message_lines.append(
                "- %s: %s" % (
                    (line.name or "").split("\n")[0],
                    item["reason"],
                )
            )

        message_lines.append("")
        message_lines.append(_("Please remove these items from your cart and choose another time."))

        return "\n".join(message_lines)


    def _chaitanya_validate_booking_lines(self):
        self.ensure_one()

        message = self._chaitanya_invalid_booking_message()

        if message:
            raise UserError(message)

        return True

    def action_confirm(self):
        for order in self:
            order._chaitanya_validate_booking_lines()

        res = super().action_confirm()

        self._create_chaitanya_bookings_from_order()

        return res

    def _cart_find_product_line(self, product_id=None, line_id=None, **kwargs):
        if self.env.context.get("chaitanya_force_new_booking_line"):
            return self.env["sale.order.line"]

        return super()._cart_find_product_line(
            product_id=product_id,
            line_id=line_id,
            **kwargs
        )


