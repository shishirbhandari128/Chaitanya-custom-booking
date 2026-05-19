# from odoo import models, fields

# class ProductTemplate(models.Model):
#     _inherit = 'product.template'

#     # 1. This prevents the website_sale template from crashing
#     is_booking_service = fields.Boolean(
#         string="Is a Booking Service", 
#         default=False
#     )
    
#     # 2. Link your product template back to your custom service model if needed
#     appointment_service_id = fields.Many2one(
#         'chaitanya.appointment.service', 
#         string="Related Appointment Service"
#     )
    
#     # 3. Allow gift attribute matching the flag inside your appointment view
#     allow_gift = fields.Boolean(
#         string="Allow as Gift", 
#         default=True
#     )