from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def write(self, vals):
        result = super().write(vals)

        if {"payment_state", "state"}.intersection(vals):
            sale_orders = self.mapped("invoice_line_ids.sale_line_ids.order_id")

            bookings = self.env["calendar.event"].sudo().search([
                ("sale_order_id", "in", sale_orders.ids),
            ])

            if bookings:
                bookings._sync_payment_status_from_invoice()

        return result