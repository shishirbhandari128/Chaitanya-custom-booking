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

    # Link to Odoo native loyalty card
    loyalty_card_id = fields.Many2one(
        "loyalty.card",
        string="Loyalty Card",
        readonly=True,
        ondelete="set null",
        copy=False,
    )

    _sql_constraints = [
        ("code_unique", "unique(code)", "Voucher code must be unique."),
    ]

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains("discount_value", "usage_limit")
    def _check_values(self):
        for voucher in self:
            if voucher.discount_value < 0:
                raise ValidationError("Discount value cannot be negative.")
            if voucher.usage_limit < 1:
                raise ValidationError("Usage limit must be at least 1.")

    # -------------------------------------------------------------------------
    # Loyalty Program Helpers
    # -------------------------------------------------------------------------

    def _get_or_create_loyalty_program(self, discount_type, discount_value):
        """
        Find or create a loyalty.program matching the given discount config.
        Each unique (discount_type, discount_value) combination gets its own
        program so Odoo can correctly compute the discount on the order line.
        """
        LoyaltyProgram = self.env["loyalty.program"].sudo()

        reward_type = "discount"
        discount_mode = "percent" if discount_type == "percent" else "per_order"

        domain = [
            ("name", "like", "Chaitanya Voucher"),
            ("program_type", "=", "coupons"),
            ("reward_ids.reward_type", "=", reward_type),
            ("reward_ids.discount_mode", "=", discount_mode),
            ("reward_ids.discount", "=", discount_value),
        ]
        program = LoyaltyProgram.search(domain, limit=1)

        if not program:
            reward_vals = {
                "reward_type": reward_type,
                "discount_mode": discount_mode,
                "discount": discount_value,
                "discount_applicability": "order",
                "required_points": 1,
            }
            program = LoyaltyProgram.create({
                "name": f"Chaitanya Voucher [{discount_type} {discount_value}]",
                "program_type": "coupons",
                "applies_on": "current",
                "trigger": "with_code",
                "reward_ids": [(0, 0, reward_vals)],
            })

        return program

    def _build_loyalty_card_vals(self, program):
        """Return vals dict for creating/updating a loyalty.card."""
        self.ensure_one()
        return {
            "program_id": program.id,
            "code": self.code,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "expiration_date": self.expiry_date or False,
            "points": self.usage_limit - self.usage_count,
        }

    def _sync_to_loyalty_card(self):
        """Create or update the linked loyalty.card for each voucher."""
        LoyaltyCard = self.env["loyalty.card"].sudo()

        for voucher in self:
            # Only sync active vouchers; archive/delete handled separately
            if voucher.state not in ("active", "draft"):
                continue

            program = voucher._get_or_create_loyalty_program(
                voucher.discount_type, voucher.discount_value
            )
            card_vals = voucher._build_loyalty_card_vals(program)

            if voucher.loyalty_card_id:
                voucher.loyalty_card_id.write(card_vals)
            else:
                card = LoyaltyCard.create(card_vals)
                # Use write directly to avoid triggering our overridden write
                voucher.write({"loyalty_card_id": card.id})

    # -------------------------------------------------------------------------
    # ORM Overrides
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_loyalty_card()
        return records

    def write(self, vals):
        res = super().write(vals)

        # Fields that require re-syncing the loyalty card
        sync_triggers = {
            "code", "discount_type", "discount_value",
            "expiry_date", "partner_id", "state",
            "usage_limit", "usage_count",
        }
        if sync_triggers & set(vals.keys()):
            # Handle state changes first
            for voucher in self:
                if voucher.state in ("used", "expired") and voucher.loyalty_card_id:
                    # Zero out points so the code can no longer be applied
                    voucher.loyalty_card_id.sudo().write({"points": 0})
                elif voucher.state == "active":
                    voucher._sync_to_loyalty_card()

        return res

    def unlink(self):
        """Archive linked loyalty cards before deleting the voucher."""
        cards = self.mapped("loyalty_card_id").sudo()
        if cards:
            cards.write({"points": 0})  # Invalidate without hard-deleting
        return super().unlink()

    # -------------------------------------------------------------------------
    # Business Logic
    # -------------------------------------------------------------------------

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

    def action_mark_used(self):
        """Increment usage count and mark as used if limit reached."""
        for voucher in self:
            voucher.usage_count += 1
            if voucher.usage_count >= voucher.usage_limit:
                voucher.state = "used"
            # write() override will sync points to loyalty card automatically