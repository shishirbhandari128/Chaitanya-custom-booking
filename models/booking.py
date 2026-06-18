from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    provider_id = fields.Many2one(
        "chaitanya.appointment.provider",
        string="Therapist",
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

    product_id = fields.Many2one("product.product", string="Product Variant", readonly=True, copy=False)

    product_template_id = fields.Many2one(
        "product.template",
        string="Product",
        related="product_id.product_tmpl_id",
        store=True,
        readonly=True,
    )

    product_variant_description = fields.Char(string="Selected Variant", readonly=True, copy=False)

    customer_name = fields.Char()
    customer_email = fields.Char()
    customer_phone = fields.Char()

    duration = fields.Integer(
        string="Booking Duration (Minutes)",
        copy=False,
    )

    sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True, copy=False)
    sale_order_line_id = fields.Many2one("sale.order.line", string="Sale Order Line", readonly=True, copy=False)

    sale_order_state = fields.Selection(
        related="sale_order_id.state",
        string="Sale Order Status",
        readonly=True,
    )

    related_order_booking_count = fields.Integer(
        string="Order Bookings",
        compute="_compute_order_booking_counts",
    )

    related_order_cancelled_booking_count = fields.Integer(
        string="Cancelled Order Bookings",
        compute="_compute_order_booking_counts",
    )

    order_has_non_booking_lines = fields.Boolean(
        string="Order Has Non-Booking Lines",
        compute="_compute_order_booking_counts",
    )

    sale_order_currency_id = fields.Many2one(
        "res.currency",
        related="sale_order_id.currency_id",
        string="Sale Order Currency",
        readonly=True,
        store=True,
    )

    sale_order_amount_total = fields.Monetary(
        related="sale_order_id.amount_total",
        string="Order Total",
        readonly=True,
        currency_field="sale_order_currency_id",
        store=True,
    )

    invoice_ids = fields.Many2many(
        "account.move",
        string="Invoices",
        compute="_compute_invoice_ids",
    )

    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_invoice_ids",
    )

    invoice_status = fields.Selection(
        [
            ("no_invoice", "No Invoice"),
            ("draft", "Draft"),
            ("posted_unpaid", "Posted Unpaid"),
            ("partial", "Partially Paid"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        string="Invoice Status",
        compute="_compute_invoice_status",
    )

    invoice_amount_total = fields.Monetary(
        string="Invoice Total",
        compute="_compute_invoice_amounts",
        currency_field="currency_id",
    )

    invoice_amount_residual = fields.Monetary(
        string="Amount Due",
        compute="_compute_invoice_amounts",
        currency_field="currency_id",
    )

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

    voucher_id = fields.Many2one("loyalty.card")
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    base_amount = fields.Monetary(default=0.0, currency_field="currency_id")
    discount_amount = fields.Monetary(default=0.0, currency_field="currency_id")
    final_amount = fields.Monetary(default=0.0, currency_field="currency_id")

    active_amount = fields.Monetary(
        string="Active Amount",
        compute="_compute_lifecycle_amounts",
        store=True,
        currency_field="currency_id",
    )

    refunded_amount = fields.Monetary(
        string="Refunded/Cancelled Amount",
        compute="_compute_lifecycle_amounts",
        store=True,
        currency_field="currency_id",
    )

    net_amount = fields.Monetary(
        string="Net Amount",
        compute="_compute_lifecycle_amounts",
        store=True,
        currency_field="currency_id",
    )

    

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


    def _get_order_bookings(self):
        self.ensure_one()

        if not self.sale_order_id:
            return self.env["calendar.event"]

        return self.env["calendar.event"].search([
            ("sale_order_id", "=", self.sale_order_id.id),
        ])

    def _get_booking_duration_minutes(self, appointment_type, line=False):
        if line and line.chaitanya_duration:
            return line.chaitanya_duration

        duration_hours = getattr(appointment_type, "appointment_duration", 0.0) or 0.0
        return int(duration_hours * 60)


    @api.model
    def _is_slot_available(self, appointment_type, provider, start_dt, duration=False, exclude_booking=False):
        if not appointment_type or not provider or not start_dt:
            return False

        duration_minutes = duration or int((appointment_type.appointment_duration or 0.0) * 60) or 60
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        if provider not in appointment_type.provider_ids:
            return False

        overlap_count = self.sudo().search_count(
            self._get_overlapping_booking_domain(
                provider,
                start_dt,
                end_dt,
                exclude_booking=exclude_booking,
            )
        )

        return overlap_count == 0

    @api.model
    def _get_overlapping_booking_domain(self, provider, start_dt, end_dt, exclude_booking=False):
        domain = [
            ("provider_id", "=", provider.id),
            ("start", "<", end_dt),
            ("stop", ">", start_dt),
            ("state", "=", "reserved"),
            ("appointment_type_id", "!=", False),
        ]

        if exclude_booking:
            domain.append(("id", "!=", exclude_booking.id))

        return domain

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetime_range(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime and booking.start_datetime >= booking.end_datetime:
                raise ValidationError(_("Booking end time must be after start time."))

    def action_cancel(self):
        for booking in self:
            if booking.state == "cancelled":
                continue

            booking.write({"state": "cancelled"})

            order = booking.sale_order_id
            line = booking.sale_order_line_id

            if order and line and order.state in ("draft", "sent"):
                line.sudo().unlink()

            booking._auto_cancel_sale_order_if_ready()
            booking._cancel_odoo_calendar_event()

        return True

    def action_cancel_entire_order(self):
        for booking in self:
            order = booking.sale_order_id

            if not order:
                raise UserError(_("This booking is not linked to a sale order."))

            order_bookings = booking._get_order_bookings()

            order_bookings.filtered(lambda item: item.state != "cancelled").write({
                "state": "cancelled",
            })

            if order.state != "cancel":
                order.sudo()._action_cancel()

        return True

    def action_view_related_order_bookings(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_("This booking is not linked to a sale order."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Related Order Bookings"),
            "res_model": "chaitanya.appointment.booking",
            "view_mode": "list,form",
            "domain": [("sale_order_id", "=", self.sale_order_id.id)],
            "context": {"default_sale_order_id": self.sale_order_id.id},
        }



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

    def _get_order_bookings(self):
        self.ensure_one()

        if not self.sale_order_id:
            return self.env["chaitanya.appointment.booking"]

        return self.search([
            ("sale_order_id", "=", self.sale_order_id.id),
        ])


    def _get_order_real_lines(self):
        self.ensure_one()

        if not self.sale_order_id:
            return self.env["sale.order.line"]

        return self.sale_order_id.order_line.filtered(
            lambda line: not line.display_type
        )


    def _get_order_non_booking_lines(self):
        self.ensure_one()

        return self._get_order_real_lines().filtered(
            lambda line: not line.booking_id
            and line.price_subtotal > 0
            and not getattr(line, "is_delivery", False)
        )


    def _all_order_bookings_cancelled(self):
        self.ensure_one()

        order_bookings = self._get_order_bookings()

        return bool(order_bookings) and all(
            booking.state == "cancelled"
            for booking in order_bookings
        )


  
    def _can_auto_cancel_sale_order(self):
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)

        order = self.sale_order_id

        if not order:
            _logger.warning("AUTO-CANCEL: No order linked to booking %s", self.name)
            return False

        if order.state == "cancel":
            _logger.warning("AUTO-CANCEL: Order %s already cancelled", order.name)
            return False

        blocking_lines = order.order_line.filtered(
            lambda line: not line.display_type
            and not line.booking_id
            and line.price_subtotal > 0
            and not getattr(line, "is_delivery", False)
        )

        if blocking_lines:
            _logger.warning(
                "AUTO-CANCEL BLOCKED by lines: %s | price_subtotals: %s",
                blocking_lines.mapped("name"),
                blocking_lines.mapped("price_subtotal"),
            )
            return False

        all_cancelled = self._all_order_bookings_cancelled()
        _logger.warning(
            "AUTO-CANCEL: all_bookings_cancelled=%s for order %s | bookings: %s | states: %s",
            all_cancelled,
            order.name,
            self._get_order_bookings().mapped("name"),
            self._get_order_bookings().mapped("state"),
        )
        return all_cancelled


    def _auto_cancel_sale_order_if_ready(self):
        import logging
        _logger = logging.getLogger(__name__)

        for booking in self:
            order = booking.sale_order_id

            if not order:
                continue

            _logger.warning(
                "AUTO-CANCEL CHECK: booking=%s order=%s order_state=%s",
                booking.name, order.name, order.state,
            )

            if booking._can_auto_cancel_sale_order():
                all_lines = order.order_line.filtered(lambda l: not l.display_type)
                _logger.warning(
                    "AUTO-CANCEL PRE-CLEANUP lines: %s | booking_ids: %s | price_subtotals: %s",
                    all_lines.mapped("name"),
                    all_lines.mapped("booking_id.name"),
                    all_lines.mapped("price_subtotal"),
                )

                leftover_lines = order.order_line.filtered(
                    lambda line: not line.display_type
                    and not line.booking_id
                    and not getattr(line, "is_delivery", False)
                )

                if leftover_lines:
                    _logger.warning(
                        "AUTO-CANCEL CLEANUP removing lines: %s | prices: %s",
                        leftover_lines.mapped("name"),
                        leftover_lines.mapped("price_subtotal"),
                    )
                    leftover_lines.sudo().unlink()
                else:
                    _logger.warning("AUTO-CANCEL CLEANUP: no leftover lines to remove")

                _logger.warning("AUTO-CANCEL EXECUTING for order %s", order.name)
                order.sudo()._action_cancel()  # <-- bypasses wizard, cancels directly
                _logger.warning(
                    "AUTO-CANCEL DONE for order %s | new_state=%s",
                    order.name, order.state,
                )

    def _compute_order_booking_counts(self):
        for booking in self:
            order_bookings = booking._get_order_bookings() if booking.sale_order_id else self.env["chaitanya.appointment.booking"]
            non_booking_lines = booking._get_order_non_booking_lines() if booking.sale_order_id else self.env["sale.order.line"]

            booking.related_order_booking_count = len(order_bookings)
            booking.related_order_cancelled_booking_count = len(
                order_bookings.filtered(lambda item: item.state == "cancelled")
            )
            booking.order_has_non_booking_lines = bool(non_booking_lines)


    def _compute_invoice_ids(self):
        for booking in self:
            invoices = booking.sale_order_id.invoice_ids.filtered(
                lambda inv: inv.move_type == "out_invoice"
            )
            booking.invoice_ids = invoices
            booking.invoice_count = len(invoices)


    def _compute_invoice_status(self):
        for booking in self:
            all_invoices = booking.invoice_ids

            if not all_invoices:
                booking.invoice_status = "no_invoice"
                continue

            active_invoices = all_invoices.filtered(lambda inv: inv.state != "cancel")

            if not active_invoices:
                booking.invoice_status = "cancelled"
            elif any(inv.state == "draft" for inv in active_invoices):
                booking.invoice_status = "draft"
            elif all(inv.payment_state == "paid" for inv in active_invoices):
                booking.invoice_status = "paid"
            elif any(inv.payment_state == "partial" for inv in active_invoices):
                booking.invoice_status = "partial"
            else:
                booking.invoice_status = "posted_unpaid"


    def _compute_invoice_amounts(self):
        for booking in self:
            invoices = booking.invoice_ids.filtered(lambda inv: inv.state != "cancel")
            booking.invoice_amount_total = sum(invoices.mapped("amount_total"))
            booking.invoice_amount_residual = sum(invoices.mapped("amount_residual"))

    @api.depends("state", "final_amount")
    def _compute_lifecycle_amounts(self):
        for booking in self:
            if booking.state == "cancelled":
                booking.active_amount = 0.0
                booking.refunded_amount = booking.final_amount
                booking.net_amount = 0.0
            else:
                booking.active_amount = booking.final_amount
                booking.refunded_amount = 0.0
                booking.net_amount = booking.final_amount


    def _sync_payment_status_from_invoice(self):
        for booking in self:
            invoices = booking.invoice_ids.filtered(lambda inv: inv.state != "cancel")

            if invoices and all(inv.payment_state == "paid" for inv in invoices):
                booking.payment_status = "paid"
            elif invoices:
                booking.payment_status = "pending"
            else:
                booking.payment_status = "unpaid"


    def action_confirm_sale_order(self):
        for booking in self:
            order = booking.sale_order_id

            if not order:
                raise ValidationError(_("This booking is not linked to a sale order."))

            if order.state in ("draft", "sent"):
                order.sudo().action_confirm()

        return True


    def action_create_invoice(self):
        self.ensure_one()

        order = self.sale_order_id

        if not order:
            raise ValidationError(_("This booking is not linked to a sale order."))

        if order.state in ("draft", "sent"):
            order.sudo().action_confirm()

        invoices = order.sudo()._create_invoices()

        if invoices:
            self._sync_payment_status_from_invoice()

        return self.action_view_invoices()


    def action_view_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise ValidationError(_("This booking is not linked to a sale order."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Order"),
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }


    def action_view_invoices(self):
        self.ensure_one()

        invoices = self.invoice_ids

        return {
            "type": "ir.actions.act_window",
            "name": _("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
            "context": {
                "default_move_type": "out_invoice",
            },
        }


    def action_sync_payment_status(self):
        self._sync_payment_status_from_invoice()
        return True

    def unlink(self):
        orders = self.mapped("sale_order_id")

        for booking in self:
            if booking.state != "cancelled":
                raise UserError(_("You must cancel this booking before deleting it."))

            order = booking.sale_order_id

            if order and order.state not in ("draft", "sent", "cancel"):
                raise UserError(_(
                    "You can delete this booking only after the related sale order is cancelled."
                ))

        result = super().unlink()

        Booking = self.env["chaitanya.appointment.booking"].sudo()

        for order in orders.sudo():
            if not order.exists():
                continue

            remaining_bookings = Booking.search_count([
                ("sale_order_id", "=", order.id),
            ])

            if remaining_bookings:
                continue

            if order.state in ("draft", "sent", "cancel"):
                order.unlink()

        return result













