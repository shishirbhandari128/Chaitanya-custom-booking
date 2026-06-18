from odoo import api, fields, models


class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    description = fields.Text(translate=True)
    image = fields.Binary(attachment=True)
    website_published = fields.Boolean(default=True)
    service_count = fields.Integer(compute="_compute_service_count")

    def _compute_service_count(self):
        grouped = self.env["chaitanya.appointment.service"].read_group(
            [("category_id", "in", self.ids)],
            ["category_id"],
            ["category_id"],
        )
        counts = {row["category_id"][0]: row["category_id_count"] for row in grouped}
        for category in self:
            category.service_count = counts.get(category.id, 0)


