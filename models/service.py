from odoo import api, fields, models

# =================================================================
# 1. TELL ODOO'S PRODUCT SYSTEM TO ACCEPT YOUR BOOKING PROPERTIES
# =================================================================
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_booking_service = fields.Boolean(string="Is a Booking Service", default=False)
    appointment_service_id = fields.Many2one('chaitanya.appointment.service', string="Related Service")
    allow_gift = fields.Boolean(string="Allow as Gift", default=True)


# =================================================================
# YOUR ORIGINAL MODEL (With small updates to pass data to the product)
# =================================================================
class ChaitanyaAppointmentService(models.Model):
    _name = "chaitanya.appointment.service"
    _description = "Chaitanya Service"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "category_id, sequence, name"

    name = fields.Char(required=True, translate=True, tracking=True)
    sequence = fields.Integer(default=10)
    category_id = fields.Many2one("chaitanya.appointment.service.category", required=True, ondelete="restrict", tracking=True)
    short_description = fields.Char(translate=True)
    description = fields.Html(translate=True)
    benefits = fields.Html(translate=True)
    duration = fields.Integer(string="Duration (Minutes)", required=True, default=60)
    price = fields.Monetary(required=True, default=0.0)
    product_id = fields.Many2one("product.product", string="Checkout Product", copy=False)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    image = fields.Binary(attachment=True)
    provider_ids = fields.Many2many("chaitanya.appointment.provider", "chaitanya_appointment_provider_service_rel", "service_id", "provider_id", string="Therapists")
    allow_gift = fields.Boolean(default=True) # This saves to YOUR table
    active = fields.Boolean(default=True)
    website_published = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        services._ensure_checkout_product()
        return services

    def write(self, vals):
        result = super().write(vals)
        # Added "allow_gift" here so if you change it on your form, it syncs immediately!
        sync_fields = {"name", "price", "image", "website_published", "active", "product_id", "allow_gift"}
        if sync_fields.intersection(vals):
            self._ensure_checkout_product()
            self._sync_checkout_product()
        return result

    def action_ensure_checkout_product(self):
        self._ensure_checkout_product()
        self._sync_checkout_product()
        return True

    def _checkout_product_values(self):
        self.ensure_one()
        ProductTemplate = self.env["product.template"].sudo()
        
        values = {
            "name": self.name,
            "list_price": self.price,
            "sale_ok": True,
            "purchase_ok": False,
            
            # ADD THESE 3 LINES: Pass your data into the Odoo Product Template columns
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

        if self.category_id.ecommerce_category_id:
            values["public_categ_ids"] = [(6, 0, [self.category_id.ecommerce_category_id.id])]

        return values

    def _ensure_checkout_product(self):
        ProductTemplate = self.env["product.template"].sudo()
        for service in self:
            if service.product_id:
                continue
            template = ProductTemplate.create(service._checkout_product_values())
            service.product_id = template.product_variant_id.id

    def _sync_checkout_product(self):
        for service in self.filtered("product_id"):
            template = service.product_id.product_tmpl_id.sudo()
            values = service._checkout_product_values()
            template.write(values)

    def unlink(self):
        for service in self:
            if service.product_id:
                service.product_id.product_tmpl_id.unlink()
        return super().unlink()