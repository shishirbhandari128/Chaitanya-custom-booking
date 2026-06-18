# from odoo import api, fields, models
# from odoo.exceptions import ValidationError


# class LoyaltyCard(models.Model):
#     _inherit = "loyalty.card"

#     # usage_count = usage_limit - points (points decrements on each use natively)
#     # expiration_date, partner_id, code — already on loyalty.card natively
#     # state — don't store, just use a property or compute only where needed

#     def compute_discount(self, amount):
#         self.ensure_one()
#         reward = self.program_id.reward_ids[:1]
#         if not reward:
#             return 0.0
#         if reward.discount_mode == "percent":
#             return min(amount, amount * (reward.discount / 100.0))
#         return min(amount, reward.discount)

#     def is_valid_for_partner(self, partner=False):
#         self.ensure_one()
#         today = fields.Date.context_today(self)
#         if self.expiration_date and self.expiration_date < today:
#             return False
#         if self.points <= 0:
#             return False
#         if self.partner_id and (not partner or self.partner_id != partner):
#             return False
#         return True

#     def action_mark_used(self):
#         for card in self:
#             card.points = max(0, card.points - 1)