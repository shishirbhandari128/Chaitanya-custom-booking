from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ChaitanyaAppointmentVoucher(models.Model):
    _name = "chaitanya.appointment.voucher"
    _description = "Chaitanya Voucher"
    _order = "expiry_date desc, code"

    code = fields.Char(required=True)
    voucher_type = fields.Selection(
        [("discount", "Discount"), ("gift", "Gift Voucher")],
        required=True,
        default="discount",
    )
    discount_type = fields.Selection(
        [("fixed", "Fixed Amount"), ("percent", "Percentage")],
        required=True,
        default="fixed",
    )
    discount_value = fields.Float(required=True)
    expiry_date = fields.Date()
    partner_id = fields.Many2one("res.partner", string="Customer")
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("used", "Used"), ("expired", "Expired")],
        default="active",
        required=True,
    )
    usage_limit = fields.Integer(default=1)
    usage_count = fields.Integer(default=0, readonly=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Voucher code must be unique."),
    ]

    @api.constrains("discount_value", "usage_limit")
    def _check_values(self):
        for voucher in self:
            if voucher.discount_value < 0:
                raise ValidationError("Discount value cannot be negative.")
            if voucher.usage_limit < 1:
                raise ValidationError("Usage limit must be at least 1.")

    def compute_discount(self, amount):
        self.ensure_one()
        if self.discount_type == "percent":
            return min(amount, amount * (self.discount_value / 100.0))
        return min(amount, self.discount_value)

    def is_valid_for_partner(self, partner=False):
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.state != "active":
            return False
        if self.expiry_date and self.expiry_date < today:
            return False
        if self.usage_count >= self.usage_limit:
            return False
        if self.partner_id and (not partner or self.partner_id != partner):
            return False
        return True
