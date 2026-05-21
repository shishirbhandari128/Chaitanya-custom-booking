from odoo import fields, http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from datetime import datetime, timedelta, time
import pytz


class ChaitanyaWebsiteSale(WebsiteSale):

    @http.route([
        '/service',
        '/service/page/<int:page>',
        '/service/category/<model("product.public.category"):category>',
    ], type='http', auth="public", website=True)
    
    def service_shop(self, page=0, category=None, search='', **kwargs):

        return super().shop(
            page=page,
            category=category,
            search=search,
            **kwargs
        )


class ChaitanyaAppointmentController(http.Controller):
    def _booking_error(self, message):
        return request.render("chaitanya_booking_flow.booking_error_page", {"message": message})

    


    # @http.route(["/chaitanya/services"], type="http", auth="public", website=True, sitemap=True)
    # def services_page(self, category=None, category_id=None, **kwargs):
    #     selected_category_id = category or category_id
    #     Category = request.env["chaitanya.appointment.service.category"].sudo()
    #     Service = request.env["chaitanya.appointment.service"].sudo()
    #     categories = Category.search([("active", "=", True), ("website_published", "=", True)])
    #     domain = [("active", "=", True), ("website_published", "=", True)]
    #     selected_category = False
    #     if selected_category_id:
    #         selected_category = Category.browse(int(selected_category_id))
    #         if selected_category.exists():
    #             domain.append(("category_id", "=", selected_category.id))
    #     services = Service.search(domain, order="category_id, sequence, name")
    #     return request.render(
    #         "chaitanya_booking_flow.services_page",
    #         {
    #             "categories": categories,
    #             "services": services,
    #             "selected_category": selected_category,
    #             "active_category_id": selected_category.id if selected_category else False,
    #         },
    #     )

    # @http.route(
    #     ["/chaitanya/service/<int:service_id>"],
    #     type="http",
    #     auth="public",
    #     website=True,
    # )
    # def service_detail(self, service_id, **kwargs):
    #     service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)
    #     if not service.exists() or not service.active or not service.website_published:
    #         return request.not_found()
    #     return request.render("chaitanya_booking_flow.service_detail_page", {"service": service})

    @http.route("/booking/start/<int:service_id>", type="http", auth="public", website=True, page=True)
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

    def _booking_timezone(self):
        tz_name = (
            request.env.context.get("tz")
            or request.env.user.tz
            or request.website.user_id.tz
            or "Asia/Kathmandu"
        )
        return pytz.timezone(tz_name)


    def _now_local(self):
        tz = self._booking_timezone()
        return fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(tz)


    def _float_to_local_datetime(self, date_value, hour):
        if isinstance(date_value, str):
            date_value = fields.Date.from_string(date_value)

        hours = int(hour)
        minutes = int(round((hour - hours) * 60))

        naive_dt = datetime.combine(date_value, time(hour=hours, minute=minutes))
        return self._booking_timezone().localize(naive_dt)


    def _local_datetime_to_utc_string(self, local_dt):
        utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
        return fields.Datetime.to_string(utc_dt)


    def _get_provider_slots(self, service, provider, date_value):
        slots = []
        now_local = self._now_local()

        if isinstance(date_value, str):
            date_value = fields.Date.from_string(date_value)

        templates = provider.weekly_template_ids.filtered(lambda t: t.active)

        for template in templates:
            schedule_dates = template.date_ids.filtered(lambda d: d.date == date_value)

            for schedule_date in schedule_dates:
                for slot in schedule_date.slot_ids:
                    if slot.is_off:
                        continue

                    current = self._float_to_local_datetime(schedule_date.date, slot.start_hour)
                    end_dt = self._float_to_local_datetime(schedule_date.date, slot.end_hour)

                    while current + timedelta(minutes=service.duration) <= end_dt:
                        start_utc = fields.Datetime.from_string(self._local_datetime_to_utc_string(current))

                        if (
                            current > now_local
                            and request.env["chaitanya.appointment.booking"].sudo()._is_slot_available(
                                service,
                                provider,
                                start_utc,
                            )
                        ):
                            slots.append({
                                "value": self._local_datetime_to_utc_string(current),
                                "label": current.strftime("%I:%M %p"),
                            })

                        current += timedelta(minutes=slot.slot_interval or 30)

        return sorted(slots, key=lambda s: s["value"])


    def _provider_card(self, service, provider, date_value=False):
        all_slots = []

        if date_value:
            all_slots = self._get_provider_slots(service, provider, date_value)
        else:
            today = fields.Date.context_today(request.env.user)

            schedule_dates = provider.weekly_template_ids.filtered(
                lambda t: t.active
            ).mapped("date_ids")

            schedule_dates = schedule_dates.filtered(lambda d: d.date >= today)

            for schedule_date in sorted(schedule_dates, key=lambda d: d.date):
                all_slots = self._get_provider_slots(service, provider, schedule_date.date)
                if all_slots:
                    break

        if not all_slots:
            return False

        nearest = all_slots[0]

        return {
            "id": provider.id,
            "name": provider.name,
            "specialization": provider.specialization or "",
            "image_url": "/web/image/chaitanya.appointment.provider/%s/image" % provider.id,
            "nearest_time": nearest["label"],
            "nearest_date": nearest["value"][:10],
            "slots": all_slots,
        }

    @http.route("/booking/select/<int:service_id>/<string:method>", type="http", auth="public", website=True)
    def booking_select(self, service_id, method, gift="0", **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)

        if method not in ("therapist", "availability"):
            return request.not_found()

        if not service.exists() or not service.active or not service.website_published:
            return request.not_found()

        is_gift = gift in ("1", "true", "True")

        return request.render("chaitanya_booking_flow.booking_select_page", {
            "service": service,
            "booking_method": method,
            "is_gift": is_gift,
        })

    @http.route("/booking/get_therapist_cards", type="json", auth="public", website=True)
    def get_therapist_cards(self, service_id, date=False, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))

        if not service.exists():
            return []

        date_value = fields.Date.from_string(date) if date else False
        providers = service.provider_ids.filtered(lambda p: p.active and p.is_active_for_booking)

        cards = []
        for provider in providers:
            card = self._provider_card(service, provider, date_value)
            if card:
                cards.append(card)

        return sorted(cards, key=lambda c: (c["nearest_date"], c["nearest_time"], c["name"].lower()))

    @http.route("/booking/get_provider_dates", type="json", auth="public", website=True)
    def get_provider_dates(self, service_id, provider_id, **kwargs):
        provider = request.env["chaitanya.appointment.provider"].sudo().browse(int(provider_id))
        dates = provider.weekly_template_ids.filtered(lambda t: t.active).mapped("date_ids")
        dates = dates.filtered(lambda d: d.date >= fields.Date.today())

        return sorted(set(fields.Date.to_string(d.date) for d in dates))

    @http.route("/booking/get_provider_slots", type="json", auth="public", website=True)
    def get_provider_slots(self, service_id, provider_id, date, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        provider = request.env["chaitanya.appointment.provider"].sudo().browse(int(provider_id))
        date_value = fields.Date.from_string(date)

        return self._get_provider_slots(service, provider, date_value)

    
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
        
        service._ensure_checkout_product()
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


    @http.route("/booking/cart/remove/<int:line_id>", type="http", auth="public", website=True)
    def remove_cart_booking_line(self, line_id, **kwargs):
        order = request.website.sale_get_order()
        if not order:
            return request.redirect("/shop/cart")

        line = request.env["sale.order.line"].sudo().browse(line_id)

        if line.exists() and line.order_id.id == order.id:
            order._cart_update(
                product_id=line.product_id.id,
                line_id=line.id,
                set_qty=0,
            )

        return request.redirect("/shop/cart")
