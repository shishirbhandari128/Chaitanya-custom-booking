
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_booking_service = fields.Boolean(string="Is a Booking Service", default=False)
    appointment_service_id = fields.Many2one(
        "chaitanya.appointment.service",
        string="Related Service",
        ondelete="set null",
    )
    allow_gift = fields.Boolean(string="Allow as Gift", default=True)


class ChaitanyaAppointmentService(models.Model):
    _name = "chaitanya.appointment.service"
    _description = "Chaitanya Service"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, tracking=True)
    sequence = fields.Integer(default=10)

    category_id = fields.Many2many(
        "chaitanya.appointment.service.category",
        "chaitanya_service_category_rel",
        "service_id",
        "category_id",
        string="Categories",
        tracking=True,
    )

    short_description = fields.Char(translate=True)
    description = fields.Html(translate=True)
    benefits = fields.Html(translate=True)

    duration = fields.Integer(string="Duration (Minutes)", required=True, default=60)
    price = fields.Monetary(required=True, default=0.0)

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    attribute_line_ids = fields.One2many(
        "chaitanya.service.attribute.line",
        "service_id",
        string="Service Options",
    )

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

    attribute_line_ids = fields.One2many(
        "chaitanya.service.attribute.line",
        "service_id",
        string="Service Options",
    )

    image = fields.Binary(attachment=True)

    provider_ids = fields.Many2many(
        "chaitanya.appointment.provider",
        "chaitanya_appointment_provider_service_rel",
        "service_id",
        "provider_id",
        string="Therapists",
    )

    allow_gift = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
    website_published = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        services._ensure_checkout_product()
        services.option_line_ids.sync_to_product_attributes()
        return services

    def write(self, vals):
        result = super().write(vals)

        if self.env.context.get("skip_checkout_product_sync"):
            return result

        sync_fields = {
            "name",
            "price",
            "category_id",
            "image",
            "website_published",
            "active",
            "allow_gift",
        }

        if sync_fields.intersection(vals):
            self._ensure_checkout_product()
            self._sync_checkout_product()

        return result

    def action_ensure_checkout_product(self):
        self._ensure_checkout_product()
        self._sync_checkout_product()
        self.option_line_ids.sync_to_product_attributes()
        return True

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

    def _checkout_product_values(self):
        self.ensure_one()
        ProductTemplate = self.env["product.template"].sudo()

        values = {
            "name": self.name,
            "list_price": self.price,
            "sale_ok": True,
            "purchase_ok": False,
            "is_booking_service": True,
            "appointment_service_id": self.id,
            "allow_gift": self.allow_gift,
        }

        if "detailed_type" in ProductTemplate._fields:
            values["detailed_type"] = "service"
        else:
            values["type"] = "service"

        if "image_1920" in ProductTemplate._fields and self.image:
            values["image_1920"] = self.image

        if "website_published" in ProductTemplate._fields:
            values["website_published"] = self.website_published

        ecommerce_categories = self.category_id.mapped("ecommerce_category_id").ids
        values["public_categ_ids"] = [(6, 0, ecommerce_categories)]

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

    def unlink(self):
        templates = self.mapped("product_tmpl_id").sudo()
        result = super().unlink()

        if templates:
            templates.unlink()

        return result


from odoo import api, fields, models


class ChaitanyaServiceAttribute(models.Model):
    _name = "chaitanya.service.attribute"
    _description = "Chaitanya Service Attribute"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)

    display_type = fields.Selection(
        [
            ("radio", "Radio"),
            ("pills", "Pills"),
            ("select", "Select"),
            ("color", "Color"),
            ("multi", "Multi-checkbox"),
        ],
        default="radio",
        required=True,
    )

    create_variant = fields.Selection(
        [
            ("always", "Instantly"),
            ("dynamic", "Dynamically"),
            ("no_variant", "Never"),
        ],
        default="always",
        required=True,
    )

    ecommerce_filter_visible = fields.Boolean(default=True)

    product_attribute_id = fields.Many2one(
        "product.attribute",
        string="Synced eCommerce Attribute",
        readonly=True,
        copy=False,
    )

    value_ids = fields.One2many(
        "chaitanya.service.attribute.value",
        "attribute_id",
        string="Attribute Values",
    )

    def _product_attribute_vals(self):
        self.ensure_one()
        ProductAttribute = self.env["product.attribute"]

        vals = {
            "name": self.name,
            "create_variant": self.create_variant,
        }

        if "display_type" in ProductAttribute._fields:
            vals["display_type"] = self.display_type

        if "visibility" in ProductAttribute._fields:
            vals["visibility"] = "visible" if self.ecommerce_filter_visible else "hidden"

        return vals

    def sync_to_ecommerce_attribute(self):
        ProductAttribute = self.env["product.attribute"].sudo()

        for attribute in self:
            product_attribute = attribute.product_attribute_id

            if product_attribute:
                product_attribute.write(attribute._product_attribute_vals())
            else:
                product_attribute = ProductAttribute.create(attribute._product_attribute_vals())
                attribute.sudo().write({
                    "product_attribute_id": product_attribute.id,
                })

            attribute.value_ids.sync_to_ecommerce_value()

        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.sync_to_ecommerce_attribute()
        return records

    def write(self, vals):
        result = super().write(vals)

        if {"name", "display_type", "create_variant", "ecommerce_filter_visible"}.intersection(vals):
            self.sync_to_ecommerce_attribute()
            self.env["chaitanya.service.attribute.line"].search([
                ("attribute_id", "in", self.ids),
            ]).sync_to_product_template()

        return result


class ChaitanyaServiceAttributeValue(models.Model):
    _name = "chaitanya.service.attribute.value"
    _description = "Chaitanya Service Attribute Value"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)

    attribute_id = fields.Many2one(
        "chaitanya.service.attribute",
        required=True,
        ondelete="cascade",
    )

    name = fields.Char(required=True)
    default_extra_price = fields.Float(string="Default Extra Price", default=0.0)

    product_attribute_value_id = fields.Many2one(
        "product.attribute.value",
        string="Synced eCommerce Value",
        readonly=True,
        copy=False,
    )

    def _product_attribute_value_vals(self):
        self.ensure_one()

        product_attribute = self.attribute_id.product_attribute_id

        if not product_attribute:
            self.attribute_id.with_context(skip_value_sync=True).sync_to_ecommerce_attribute()
            product_attribute = self.attribute_id.product_attribute_id

        vals = {
            "name": self.name,
            "attribute_id": product_attribute.id,
        }

        if "default_extra_price" in self.env["product.attribute.value"]._fields:
            vals["default_extra_price"] = self.default_extra_price

        return vals

    def sync_to_ecommerce_value(self):
        ProductAttributeValue = self.env["product.attribute.value"].sudo()

        for value in self:
            if not value.attribute_id.product_attribute_id:
                value.attribute_id.with_context(skip_value_sync=True).sync_to_ecommerce_attribute()

            product_value = value.product_attribute_value_id

            if product_value:
                product_value.write(value._product_attribute_value_vals())
            else:
                product_value = ProductAttributeValue.create(value._product_attribute_value_vals())
                value.sudo().write({
                    "product_attribute_value_id": product_value.id,
                })

        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.sync_to_ecommerce_value()
        return records

    def write(self, vals):
        result = super().write(vals)

        if {"name", "default_extra_price", "attribute_id"}.intersection(vals):
            self.sync_to_ecommerce_value()
            self.env["chaitanya.service.attribute.line"].search([
                ("value_ids", "in", self.ids),
            ]).sync_to_product_template()

        return result



class ChaitanyaServiceAttributeLine(models.Model):
    _name = "chaitanya.service.attribute.line"
    _description = "Chaitanya Service Attribute Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)

    service_id = fields.Many2one(
        "chaitanya.appointment.service",
        required=True,
        ondelete="cascade",
    )

    attribute_id = fields.Many2one(
        "chaitanya.service.attribute",
        string="Attribute",
        required=True,
    )

    value_ids = fields.Many2many(
        "chaitanya.service.attribute.value",
        "chaitanya_service_attr_line_value_rel",
        "line_id",
        "value_id",
        string="Values",
    )

    product_attribute_line_id = fields.Many2one(
        "product.template.attribute.line",
        string="Synced Product Attribute Line",
        readonly=True,
        copy=False,
    )

    def sync_to_product_template(self):
        ProductTemplateAttributeLine = self.env["product.template.attribute.line"].sudo()

        for line in self:
            service = line.service_id
            service._ensure_checkout_product()

            template = service.product_tmpl_id.sudo()

            line.attribute_id.sync_to_ecommerce_attribute()
            line.value_ids.sync_to_ecommerce_value()

            product_attribute = line.attribute_id.product_attribute_id
            product_values = line.value_ids.mapped("product_attribute_value_id")

            product_line = line.product_attribute_line_id
            if not product_line:
                product_line = ProductTemplateAttributeLine.search([
                    ("product_tmpl_id", "=", template.id),
                    ("attribute_id", "=", product_attribute.id),
                ], limit=1)

            if product_values:
                vals = {
                    "product_tmpl_id": template.id,
                    "attribute_id": product_attribute.id,
                    "value_ids": [(6, 0, product_values.ids)],
                }

                if product_line:
                    product_line.write(vals)
                else:
                    product_line = ProductTemplateAttributeLine.create(vals)

                line.sudo().write({
                    "product_attribute_line_id": product_line.id,
                })

                product_line.invalidate_recordset()

                price_by_value_id = {
                    value.product_attribute_value_id.id: value.default_extra_price
                    for value in line.value_ids
                }

                for template_value in product_line.product_template_value_ids:
                    product_value_id = template_value.product_attribute_value_id.id
                    if product_value_id in price_by_value_id:
                        template_value.sudo().write({
                            "price_extra": price_by_value_id[product_value_id],
                        })

                template._create_variant_ids()

                if template.product_variant_id:
                    service.with_context(skip_checkout_product_sync=True).write({
                        "product_id": template.product_variant_id.id,
                    })

            elif product_line:
                product_line.unlink()
                line.sudo().write({
                    "product_attribute_line_id": False,
                })

        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.sync_to_product_template()
        return records

    def write(self, vals):
        result = super().write(vals)

        if {"attribute_id", "value_ids"}.intersection(vals):
            self.sync_to_product_template()

        return result

    def unlink(self):
        product_lines = self.mapped("product_attribute_line_id").sudo()
        result = super().unlink()

        if product_lines:
            product_lines.unlink()

        return result
# from odoo import api, fields, models

# class ProductTemplate(models.Model):
#     _inherit = 'product.template'

#     is_booking_service = fields.Boolean(string="Is a Booking Service", default=False)
#     appointment_service_id = fields.Many2one('chaitanya.appointment.service', string="Related Service")
#     allow_gift = fields.Boolean(string="Allow as Gift", default=True)

# class ChaitanyaAppointmentService(models.Model):
#     _name = "chaitanya.appointment.service"
#     _description = "Chaitanya Service"
#     _inherit = ["mail.thread", "mail.activity.mixin"]
#     _order = "sequence, name"

#     name = fields.Char(required=True, translate=True, tracking=True)
#     sequence = fields.Integer(default=10)
#     category_id = fields.Many2many(
#         "chaitanya.appointment.service.category",
#         "chaitanya_service_category_rel",
#         "service_id",
#         "category_id",
#         string="Categories",
#         tracking=True
#     )
#     short_description = fields.Char(translate=True)
#     description = fields.Html(translate=True)
#     benefits = fields.Html(translate=True)
#     duration = fields.Integer(string="Duration (Minutes)", required=True, default=60)
#     price = fields.Monetary(required=True, default=0.0)
#     product_id = fields.Many2one("product.product", string="Checkout Product", copy=False)
#     currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
#     image = fields.Binary(attachment=True)
#     provider_ids = fields.Many2many("chaitanya.appointment.provider", "chaitanya_appointment_provider_service_rel", "service_id", "provider_id", string="Therapists")
#     allow_gift = fields.Boolean(default=True) # This saves to YOUR table
#     active = fields.Boolean(default=True)
#     website_published = fields.Boolean(default=True)

#     @api.model_create_multi
#     def create(self, vals_list):
#         services = super().create(vals_list)
#         services._ensure_checkout_product()
#         return services

#     def write(self, vals):
#         result = super().write(vals)
#         # Added "allow_gift" here so if you change it on your form, it syncs immediately!
#         sync_fields = {"name", "price","category_id", "image", "website_published", "active", "product_id", "allow_gift"}
#         if sync_fields.intersection(vals):
#             self._ensure_checkout_product()
#             self._sync_checkout_product()
#         return result

#     def action_ensure_checkout_product(self):
#         self._ensure_checkout_product()
#         self._sync_checkout_product()
#         return True

#     def _checkout_product_values(self):
#         self.ensure_one()
#         ProductTemplate = self.env["product.template"].sudo()
        
#         values = {
#             "name": self.name,
#             "list_price": self.price,
#             "sale_ok": True,
#             "purchase_ok": False,
            
#             # ADD THESE 3 LINES: Pass your data into the Odoo Product Template columns
#             "is_booking_service": True, 
#             "appointment_service_id": self.id,
#             "allow_gift": self.allow_gift, 
#         }
#         if "detailed_type" in ProductTemplate._fields:
#             values["detailed_type"] = "service"
#         else:
#             values["type"] = "service"
#         if "image_1920" in ProductTemplate._fields and self.image:
#             values["image_1920"] = self.image
#         if "website_published" in ProductTemplate._fields:
#             values["website_published"] = self.website_published

#         ecommerce_categories = self.category_id.mapped("ecommerce_category_id").ids
#         if ecommerce_categories:
#             values["public_categ_ids"] = [(6, 0, ecommerce_categories)]

#         return values

#     def _ensure_checkout_product(self):
#         ProductTemplate = self.env["product.template"].sudo()
#         for service in self:
#             if service.product_id:
#                 continue
#             template = ProductTemplate.create(service._checkout_product_values())
#             service.product_id = template.product_variant_id.id

#     def _sync_checkout_product(self):
#         for service in self.filtered("product_id"):
#             template = service.product_id.product_tmpl_id.sudo()
#             values = service._checkout_product_values()
#             template.write(values)

#     def unlink(self):
#         for service in self:
#             if service.product_id:
#                 service.product_id.product_tmpl_id.unlink()
#         return super().unlink()