import json
from datetime import timedelta

from odoo import fields, http
from odoo.http import request


class ChaitanyaAppointmentController(http.Controller):
    def _booking_error(self, message):
        return request.render("chaitanya_booking_flow.booking_error_page", {"message": message})

    @http.route(["/services", "/chaitanya/services"], type="http", auth="public", website=True, sitemap=True)
    def services_page(self, category=None, category_id=None, **kwargs):
        selected_category_id = category or category_id
        Category = request.env["chaitanya.appointment.service.category"].sudo()
        Service = request.env["chaitanya.appointment.service"].sudo()
        categories = Category.search([("active", "=", True), ("website_published", "=", True)])
        domain = [("active", "=", True), ("website_published", "=", True)]
        selected_category = False
        if selected_category_id:
            selected_category = Category.browse(int(selected_category_id))
            if selected_category.exists():
                domain.append(("category_id", "=", selected_category.id))
        services = Service.search(domain, order="category_id, sequence, name")
        return request.render(
            "chaitanya_booking_flow.services_page",
            {
                "categories": categories,
                "services": services,
                "selected_category": selected_category,
                "active_category_id": selected_category.id if selected_category else False,
            },
        )

    @http.route(
        ["/services/<int:service_id>", "/chaitanya/service/<int:service_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def service_detail(self, service_id, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)
        if not service.exists() or not service.active or not service.website_published:
            return request.not_found()
        return request.render("chaitanya_booking_flow.service_detail_page", {"service": service})

    @http.route("/booking/start/<int:service_id>", type="http", auth="public", website=True)
    def booking_start(self, service_id, gift="0", **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)
        if not service.exists() or not service.active or not service.website_published:
            return request.not_found()
        is_gift = gift in ("1", "true", "True")
        if is_gift and not service.allow_gift:
            return request.not_found()
        return request.render(
            "chaitanya_booking_flow.booking_start_page",
            {"service": service, "is_gift": is_gift},
        )

    @http.route("/booking/select/<int:service_id>/<string:method>", type="http", auth="public", website=True)
    def booking_select(self, service_id, method, gift="0", **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)
        if method not in ("therapist", "availability"):
            return request.not_found()
        if not service.exists() or not service.active or not service.website_published:
            return request.not_found()
        is_gift = gift in ("1", "true", "True")
        if is_gift and not service.allow_gift:
            return request.not_found()
        return request.render(
            "chaitanya_booking_flow.booking_select_page",
            {"service": service, "booking_method": method, "is_gift": is_gift},
        )

    def _provider_payload(self, providers):
        return [
            {"id": provider.id, "name": provider.name, "specialization": provider.specialization or ""}
            for provider in providers
        ]

    @http.route("/booking/get_service_therapists", type="json", auth="public", website=True)
    def get_service_therapists(self, service_id, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not service.exists() or not service.active or not service.website_published:
            return []
        return self._provider_payload(service.provider_ids.filtered("active"))

    @http.route(["/booking/get_available_therapists", "/booking/get_therapists"], type="json", auth="public", website=True)
    def get_available_therapists(self, service_id, date=None, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not service.exists() or not service.active or not service.website_published:
            return []
        providers = service.provider_ids.filtered("active")
        if date:
            booking_model = request.env["chaitanya.appointment.booking"].sudo()
            providers = providers.filtered(
                lambda provider: bool(booking_model.get_available_slots(service.id, date, provider.id))
            )
        return self._provider_payload(providers)

    @http.route("/booking/get_available_slots", type="json", auth="public", website=True)
    def get_available_slots(self, service_id, therapist_id=None, provider_id=None, date=None, **kwargs):
        provider_id = provider_id or therapist_id
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not service.exists() or not service.active or not service.website_published:
            return []
        slots = request.env["chaitanya.appointment.booking"].sudo().get_available_slots(
            service.id,
            date,
            int(provider_id) if provider_id else None,
        )
        return slots

    @http.route("/booking/get_available_dates", type="json", auth="public", website=True)
    def get_available_dates(self, service_id, therapist_id=None, provider_id=None, **kwargs):
        provider_id = provider_id or therapist_id
        if not provider_id:
            return []
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not service.exists() or not service.active or not service.website_published:
            return []
        return request.env["chaitanya.appointment.booking"].sudo().get_available_dates(
            service.id,
            int(provider_id),
        )

    @http.route("/booking/validate_voucher", type="json", auth="public", website=True)
    def validate_voucher(self, service_id, code=None, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        voucher = False
        if code:
            voucher = request.env["chaitanya.appointment.voucher"].sudo().search([("code", "=", code.strip())], limit=1)
        if code and not voucher:
            return {"valid": False, "message": "Voucher not found."}
        partner = request.env.user.partner_id if not request.env.user._is_public() else False
        if voucher and not voucher.is_valid_for_partner(partner):
            return {"valid": False, "message": "Voucher is not valid."}
        amounts = request.env["chaitanya.appointment.booking"].sudo().prepare_amounts(service, voucher, partner)
        return {"valid": True, **amounts}

    @http.route("/chaitanya/api/slots", type="http", auth="public", methods=["GET"], csrf=False)
    def api_slots(self, service_id, date, provider_id=None, **kwargs):
        slots = request.env["chaitanya.appointment.booking"].sudo().get_available_slots(
            int(service_id),
            date,
            int(provider_id) if provider_id else None,
        )
        return request.make_response(json.dumps({"slots": slots}), headers=[("Content-Type", "application/json")])

    @http.route("/chaitanya/api/providers", type="http", auth="public", methods=["GET"], csrf=False)
    def api_providers(self, service_id, start_datetime, **kwargs):
        providers = request.env["chaitanya.appointment.booking"].sudo().get_available_providers(
            int(service_id),
            start_datetime,
        )
        return request.make_response(json.dumps({"providers": providers}), headers=[("Content-Type", "application/json")])

    @http.route("/booking/submit", type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def submit_booking(self, **post):
        try:
            service = request.env["chaitanya.appointment.service"].sudo().browse(int(post.get("service_id")))
            provider = request.env["chaitanya.appointment.provider"].sudo().browse(
                int(post.get("provider_id") or post.get("therapist_id"))
            )
            start_dt = fields.Datetime.from_string(post.get("start_datetime"))
        except (TypeError, ValueError):
            return self._booking_error("Please choose a valid service, therapist, and time slot.")
        if not service.exists() or not service.active or not service.website_published:
            return self._booking_error("The selected service is not available.")
        if not provider.exists() or provider not in service.provider_ids.filtered("active"):
            return self._booking_error("The selected therapist is not available for this service.")
        if not service.product_id:
            return self._booking_error("This service is not linked to a checkout product yet.")

        booking_model = request.env["chaitanya.appointment.booking"].sudo()
        if not booking_model._is_slot_available(service, provider, start_dt):
            return self._booking_error("The selected slot is no longer available. Please choose another time.")

        partner = request.env.user.partner_id if not request.env.user._is_public() else False
        voucher = False
        voucher_code = (post.get("voucher_code") or "").strip()
        if voucher_code:
            voucher = request.env["chaitanya.appointment.voucher"].sudo().search([("code", "=", voucher_code)], limit=1)
            if not voucher or not voucher.is_valid_for_partner(partner):
                voucher = False
        amounts = booking_model.prepare_amounts(service, voucher, partner)
        booking = booking_model.create({
            "service_id": service.id,
            "provider_id": provider.id,
            "partner_id": partner.id if partner else False,
            "customer_name": partner.name if partner else False,
            "customer_email": partner.email if partner else False,
            "customer_phone": (partner.phone or partner.mobile) if partner else False,
            "start_datetime": start_dt,
            "end_datetime": start_dt + timedelta(minutes=service.duration),
            "booking_method": post.get("booking_method") or "availability",
            "is_gift": bool(post.get("is_gift")),
            "gift_delivery_type": post.get("gift_delivery_type") or False,
            "gift_recipient_email": post.get("gift_recipient_email"),
            "gift_recipient_address": post.get("gift_recipient_address"),
            "gift_message": post.get("gift_message"),
            "voucher_id": voucher.id if voucher else False,
            "payment_method": "online",
            "notes": post.get("notes"),
            "state": "reserved",
            "payment_status": "pending",
            **amounts,
        })

        order = request.website.sale_get_order(force_create=True)
        cart_values = order._cart_update(
            product_id=service.product_id.id,
            add_qty=1,
            chaitanya_booking_id=booking.id,
        )
        line = request.env["sale.order.line"].sudo().browse(cart_values.get("line_id"))
        if not line.exists() or line.order_id.id != order.id:
            booking.action_cancel()
            return self._booking_error("We could not add this booking to your cart. Please try again.")
        line.write({"booking_id": booking.id})
        booking.write({
            "sale_order_id": order.id,
            "sale_order_line_id": line.id,
        })
        return request.redirect("/shop/cart")

    @http.route("/booking/success/<string:booking_reference>", type="http", auth="public", website=True)
    def booking_success(self, booking_reference, **kwargs):
        booking = request.env["chaitanya.appointment.booking"].sudo().search([("name", "=", booking_reference)], limit=1)
        if not booking:
            return request.not_found()
        return request.render("chaitanya_booking_flow.booking_success_page", {"booking": booking})

    @http.route("/booking/download/<string:booking_reference>", type="http", auth="public", website=True)
    def download_booking(self, booking_reference, **kwargs):
        booking = request.env["chaitanya.appointment.booking"].sudo().search([("name", "=", booking_reference)], limit=1)
        if not booking:
            return request.not_found()
        pdf, _content_type = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "chaitanya_booking_flow.action_report_booking_receipt",
            [booking.id],
        )
        return request.make_response(
            pdf,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Length", len(pdf)),
                ("Content-Disposition", 'attachment; filename="%s.pdf"' % booking.name),
            ],
        )
