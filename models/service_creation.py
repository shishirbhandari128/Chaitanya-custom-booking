from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_booking_service = fields.Boolean(string="Is a Booking Service", default=False)
    appointment_type_id = fields.Many2one(
        "appointment.type",
        string="Related Service",
        ondelete="set null",
    )
    allow_gift = fields.Boolean(string="Allow as Gift", default=True)


class AppointmentType(models.Model):
    _inherit = "appointment.type"

    short_description = fields.Char(translate=True)
    benefits = fields.Html(translate=True)

    price = fields.Monetary(required=True, default=0.0)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    category_id = fields.Many2many(
        "product.public.category",
        "chaitanya_appointment_type_category_rel",
        "appointment_type_id",
        "category_id",
        string="Categories",
    )

    allow_gift = fields.Boolean(default=True)

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Checkout Product Template",
        copy=False,
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Default Checkout Variant",
        copy=False,
        readonly=True,
    )

    provider_ids = fields.Many2many(
        "chaitanya.appointment.provider",
        "chaitanya_appointment_provider_type_rel",
        "appointment_type_id",
        "provider_id",
        string="Therapists",
    )

    # ------------------------------------------------------------------ #
    #  Computed helper — attribute lines live on product_tmpl_id directly  #
    # ------------------------------------------------------------------ #

    service_attribute_line_ids = fields.One2many(
        "product.template.attribute.line",
        related="product_tmpl_id.attribute_line_ids",
        string="Service Options",
        readonly=False,
    )

    # ------------------------------------------------------------------ #
    #  Duration resolver — called from booking controller                  #
    # ------------------------------------------------------------------ #

    def _resolve_variant_duration(self, product_variant):
        """
        Returns override_duration from the selected product variant's
        attribute values, or falls back to appointment_duration.
        Result is always in minutes.
        """
        self.ensure_one()

        for ptav in product_variant.product_template_attribute_value_ids:
            pav = ptav.product_attribute_value_id
            if pav.override_duration:
                return pav.override_duration

        return int((self.appointment_duration or 0.0) * 60) or 60

    # ------------------------------------------------------------------ #
    #  Checkout product sync                                               #
    # ------------------------------------------------------------------ #

    def _checkout_product_values(self):
        self.ensure_one()
        ProductTemplate = self.env["product.template"].sudo()

        values = {
            "name": self.name,
            "list_price": self.price,
            "sale_ok": True,
            "purchase_ok": False,
            "is_booking_service": True,
            "appointment_type_id": self.id,
            "allow_gift": self.allow_gift,
        }

        if "detailed_type" in ProductTemplate._fields:
            values["detailed_type"] = "service"
        else:
            values["type"] = "service"

        if self.image_1920:
            values["image_1920"] = self.image_1920

        if "website_published" in ProductTemplate._fields:
            values["website_published"] = self.is_published

        values["public_categ_ids"] = [(6, 0, self.category_id.ids)]

        return values

    def _ensure_checkout_product(self):
        ProductTemplate = self.env["product.template"].sudo()

        for service in self:
            if service.product_tmpl_id:
                if not service.product_id and service.product_tmpl_id.product_variant_id:
                    service.with_context(skip_checkout_product_sync=True).write({
                        "product_id": service.product_tmpl_id.product_variant_id.id,
                    })
                continue

            template = ProductTemplate.create(service._checkout_product_values())

            service.with_context(skip_checkout_product_sync=True).write({
                "product_tmpl_id": template.id,
                "product_id": template.product_variant_id.id,
            })

    def _sync_checkout_product(self):
        for service in self.filtered("product_tmpl_id"):
            template = service.product_tmpl_id.sudo()
            template.write(service._checkout_product_values())

            if template.product_variant_id:
                service.with_context(skip_checkout_product_sync=True).write({
                    "product_id": template.product_variant_id.id,
                })

    def write(self, vals):
        result = super().write(vals)

        if self.env.context.get("skip_checkout_product_sync"):
            return result

        sync_fields = {
            "name",
            "price",
            "category_id",
            "image_1920",
            "is_published",
            "active",
            "allow_gift",
        }

        if sync_fields.intersection(vals):
            self._ensure_checkout_product()
            self._sync_checkout_product()

        return result

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        services._ensure_checkout_product()
        return services

    def unlink(self):
        templates = self.mapped("product_tmpl_id").sudo()
        result = super().unlink()
        if templates:
            templates.unlink()
        return result

    def action_open_checkout_product(self):
        self.ensure_one()
        self._ensure_checkout_product()
        return {
            "type": "ir.actions.act_window",
            "name": "Checkout Product",
            "res_model": "product.template",
            "res_id": self.product_tmpl_id.id,
            "view_mode": "form",
            "target": "current",
        }

class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    is_service_attribute = fields.Boolean(
        string="Used in Services",
        default=False,
        help="When enabled, this attribute appears in the Service booking configuration.",
    )


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    override_duration = fields.Integer(
        string="Override Duration (Min)",
        default=0,
        help="Replaces the service base duration for this variant. Leave 0 to use service default.",
    )