from odoo import api, fields, models


class ChaitanyaAppointmentServiceCategory(models.Model):
    _name = "chaitanya.appointment.service.category"
    _description = "Chaitanya Service Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    image = fields.Binary(attachment=True)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean(default=True)
    service_count = fields.Integer(compute="_compute_service_count")

    # Link to eCommerce category
    ecommerce_category_id = fields.Many2one(
        "product.public.category",
        string="E‑Commerce Category",
        readonly=True,
        ondelete="cascade",
    )

    def _compute_service_count(self):
        grouped = self.env["chaitanya.appointment.service"].read_group(
            [("category_id", "in", self.ids)],
            ["category_id"],
            ["category_id"],
        )
        counts = {row["category_id"][0]: row["category_id_count"] for row in grouped}
        for category in self:
            category.service_count = counts.get(category.id, 0)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        # Create linked eCommerce category
        ecommerce_category = self.env["product.public.category"].create({
            "name": record.name,
            "sequence": record.sequence,
            "parent_id": False,  # adjust if you want hierarchy
        })
        record.ecommerce_category_id = ecommerce_category.id
        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.ecommerce_category_id:
                update_vals = {}
                if "name" in vals:
                    update_vals["name"] = rec.name
                if "sequence" in vals:
                    update_vals["sequence"] = rec.sequence
                if "active" in vals:
                    update_vals["active"] = rec.active
                if update_vals:
                    rec.ecommerce_category_id.write(update_vals)
        return res



    def unlink(self):
        for rec in self:
            if rec.ecommerce_category_id:
                rec.ecommerce_category_id.unlink()
        return super().unlink()
