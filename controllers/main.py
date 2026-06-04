from odoo import fields, http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from datetime import datetime, timedelta, time
import pytz
from logging import getLogger
import re 

_logger = getLogger(__name__)

class ChaitanyaWebsiteSale(WebsiteSale):

    @http.route([
        '/service',
        '/service/page/<int:page>',
        '/service/category/<model("product.public.category"):category>',
    ], type='http', auth="public", website=True)
    def service_shop(self, page=0, category=None, search='', **kwargs):
        return super().shop(page=page, category=category, search=search, **kwargs)


class ChaitanyaAppointmentController(http.Controller):

    # ─── Error helper ────────────────────────────────────────────────────────
    def _booking_error(self, message):
        request.session["booking_error"] = message
        return request.redirect("/booking")
    
    # def _get_booking_duration(self, service, product=False):
    #     if product and getattr(product, "chaitanya_duration", False):
    #         return product.chaitanya_duration
    #     return service.duration
    def _get_booking_duration(self, service, product=False):
        _logger.info(
            "BOOKING DURATION DEBUG | service=%s service_duration=%s product=%s product_id=%s product_display=%s direct_product_duration=%s",
            service.name,
            service.duration,
            bool(product),
            product.id if product else False,
            product.display_name if product else False,
            getattr(product, "chaitanya_duration", False) if product else False,
        )

        if product:
            duration_values = product.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id.name
                and v.attribute_id.name.lower() in ("duration", "time")
            )

            _logger.info(
                "BOOKING DURATION DEBUG | duration_attribute_values=%s",
                [(v.attribute_id.name, v.name) for v in duration_values],
            )

            for value in duration_values:
                match = re.search(r"\d+", value.name or "")
                if match:
                    duration = int(match.group())
                    _logger.info(
                        "BOOKING DURATION DEBUG | source=attribute_value attribute=%s value=%s returned_duration=%s",
                        value.attribute_id.name,
                        value.name,
                        duration,
                    )
                    return duration

            match = re.search(r"(\d+)\s*min", product.display_name or "", re.IGNORECASE)
            if match:
                duration = int(match.group(1))
                _logger.info(
                    "BOOKING DURATION DEBUG | source=product_display_name display_name=%s returned_duration=%s",
                    product.display_name,
                    duration,
                )
                return duration

        _logger.info(
            "BOOKING DURATION DEBUG | source=service_default returned_duration=%s",
            service.duration,
        )

        return service.duration
    # ─── Timezone helpers ─────────────────────────────────────────────────────
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

    # ─── Slot helpers ─────────────────────────────────────────────────────────
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
                                service, provider, start_utc,
                            )
                        ):
                            slots.append({
                                "value": self._local_datetime_to_utc_string(current),
                                "label": current.strftime("%I:%M %p"),
                            })
                        current += timedelta(minutes=slot.slot_interval or 30)

        return sorted(slots, key=lambda s: s["value"])

    def _is_selected_slot_still_valid(self, service, provider, start_dt):
        if not service.exists() or not provider.exists() or not start_dt:
            return False
        tz = self._booking_timezone()
        start_local = pytz.utc.localize(start_dt).astimezone(tz)
        selected_date = start_local.date()
        selected_value = fields.Datetime.to_string(start_dt)
        available_slots = self._get_provider_slots(service, provider, selected_date)
        return any(slot["value"] == selected_value for slot in available_slots)

    def _is_slot_already_in_cart(self, order, provider, start_dt, end_dt):
        if not order:
            return False
        for line in order.order_line:
            if not line.chaitanya_provider_id:
                continue
            if line.chaitanya_provider_id.id != provider.id:
                continue
            line_start = line.chaitanya_start_datetime
            line_end = line.chaitanya_end_datetime
            if not line_start or not line_end:
                continue
            if line_start < end_dt and line_end > start_dt:
                return True
        return False

    # ─── Auto-assign ──────────────────────────────────────────────────────────
    def _get_least_busy_provider(self, service, start_dt):
        """
        Return the next available therapist for the given service and slot.
        Excludes therapists already reserved in the current cart.
        Rotates by oldest last_auto_assigned first.
        """
        available_providers = []

        duration = duration or service.duration
        end_dt = start_dt + timedelta(minutes=duration)

        order = request.website.sale_get_order()

        providers = service.provider_ids.filtered(
            lambda p: p.active and p.is_active_for_booking
        )

        for provider in providers:
            if order and self._is_slot_already_in_cart(order, provider, start_dt, end_dt):
                continue
            if self._is_selected_slot_still_valid(service, provider, start_dt):
                available_providers.append(provider)

        if not available_providers:
            return False

        available_providers = sorted(
            available_providers,
            key=lambda p: (
                p.last_auto_assigned or datetime.min,
                (p.today_booking_count * 10) + p.future_booking_count,
                p.future_booking_count,
                p.id,
            )
        )

        chosen = available_providers[0]
        chosen.sudo().write({"last_auto_assigned": fields.Datetime.now()})
        return chosen

    # ─── Provider card helpers ────────────────────────────────────────────────
    def _provider_base_card(self, provider):
        return {
            "id": provider.id,
            "name": provider.name,
            "specialization": provider.specialization or "",
            "image_url": (
                "data:image/png;base64,%s" % provider.image.decode()
                if provider.image
                else "/web/static/img/placeholder.png"
            ),
        }

    def _provider_card_for_slot(self, service, provider, start_dt):
        if not self._is_selected_slot_still_valid(service, provider, start_dt):
            return False
        return self._provider_base_card(provider)

    def _get_providers_for_service_slot(self, service, start_dt):
        if not service.exists() or not start_dt:
            return []
        providers = service.provider_ids.filtered(lambda p: p.active and p.is_active_for_booking)
        cards = []
        for provider in providers:
            card = self._provider_card_for_slot(service, provider, start_dt)
            if card:
                cards.append(card)
        return sorted(cards, key=lambda p: p["name"].lower())

    def _provider_card(self, service, provider, date_value=False):
        all_slots = []
        if date_value:
            all_slots = self._get_provider_slots(service, provider, date_value)
        else:
            today = fields.Date.context_today(request.env.user)
            schedule_dates = provider.weekly_template_ids.filtered(
                lambda t: t.active
            ).mapped("date_ids").filtered(lambda d: d.date >= today)

            for schedule_date in sorted(schedule_dates, key=lambda d: d.date):
                all_slots = self._get_provider_slots(service, provider, schedule_date.date)
                if all_slots:
                    break

        if not all_slots:
            return False

        nearest = all_slots[0]
        return {
            **self._provider_base_card(provider),  # reuse base card
            "nearest_time": nearest["label"],
            "nearest_date": nearest["value"][:10],
            "slots": all_slots,
        }

    def _get_available_times_for_service_date(self, service, date_value):
        if isinstance(date_value, str):
            date_value = fields.Date.from_string(date_value)
        if not service.exists():
            return []
        providers = service.provider_ids.filtered(lambda p: p.active and p.is_active_for_booking)
        slots_by_value = {}
        for provider in providers:
            for slot in self._get_provider_slots(service, provider, date_value):
                if slot["value"] not in slots_by_value:
                    slots_by_value[slot["value"]] = {**slot, "provider_count": 0}
                slots_by_value[slot["value"]]["provider_count"] += 1
        return sorted(slots_by_value.values(), key=lambda s: s["value"])

    def _format_cart_slot_unavailable_message(self, unavailable_lines):
        lines = ["Some booking slots are no longer available:"]
        for item in unavailable_lines:
            lines.append("- %s | %s | %s | %s" % (
                item["service"], item["therapist"], item["date"], item["time"],
            ))
        lines.append("")
        lines.append("Please remove these items from your cart and choose another time.")
        return "\n".join(lines)

    # ─── Routes ───────────────────────────────────────────────────────────────
    @http.route("/booking/start/<int:service_id>", type="http", auth="public", website=True, page=True)
    def booking_start(self, service_id, gift="0", product_id=False, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)
        if not service.exists() or not service.active or not service.website_published:
            return request.not_found()
        is_gift = gift in ("1", "true", "True")
        if is_gift and not service.allow_gift:
            return request.not_found()
        product = service.product_id
        if product_id:
            selected_product = request.env["product.product"].sudo().browse(int(product_id))
            if selected_product.exists() and selected_product.product_tmpl_id.id == service.product_tmpl_id.id:
                product = selected_product
        return request.render("chaitanya_booking_flow.booking_start_page", {
            "service": service,
            "is_gift": is_gift,
            "product_id": product.id if product else False,
            "selected_product": product,
        })

    @http.route("/booking/select/<int:service_id>/<string:method>", type="http", auth="public", website=True)
    def booking_select(self, service_id, method, gift="0", product_id=False, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(service_id)
        if method not in ("therapist", "availability"):
            return request.not_found()
        if not service.exists() or not service.active or not service.website_published:
            return request.not_found()
        is_gift = gift in ("1", "true", "True")
        product = service.product_id
        if product_id:
            selected_product = request.env["product.product"].sudo().browse(int(product_id))
            if selected_product.exists() and selected_product.product_tmpl_id.id == service.product_tmpl_id.id:
                product = selected_product
        return request.render("chaitanya_booking_flow.booking_select_page", {
            "service": service,
            "booking_method": method,
            "is_gift": is_gift,
            "product_id": product.id if product else False,
            "selected_product": product,
        })

    @http.route("/booking/get_available_times", type="json", auth="public", website=True)
    def get_available_times(self, service_id, date, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not date:
            return []
        return self._get_available_times_for_service_date(service, date)

    @http.route("/booking/get_therapists_for_slot", type="json", auth="public", website=True)
    def get_therapists_for_slot(self, service_id, start_datetime, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not start_datetime:
            return []
        return self._get_providers_for_service_slot(service, fields.Datetime.from_string(start_datetime))

    @http.route("/booking/get_therapist_cards", type="json", auth="public", website=True)
    def get_therapist_cards(self, service_id, date=False, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        if not service.exists():
            return []
        date_value = fields.Date.from_string(date) if date else False
        providers = service.provider_ids.filtered(lambda p: p.active and p.is_active_for_booking)
        cards = [c for c in (self._provider_card(service, p, date_value) for p in providers) if c]
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
        return self._get_provider_slots(service, provider, fields.Date.from_string(date))

    @http.route("/booking/check_cart_slots", type="json", auth="public", website=True)
    def check_cart_slots(self, **kwargs):
        order = request.website.sale_get_order()
        if not order:
            return {"valid": True, "message": "", "unavailable_lines": []}

        tz = self._booking_timezone()
        unavailable_lines = []

        for line in order.order_line:
            service = line.chaitanya_service_id
            provider = line.chaitanya_provider_id
            start_dt = line.chaitanya_start_datetime
            end_dt = line.chaitanya_end_datetime

            if not service or not provider or not start_dt:
                continue

            if not self._is_selected_slot_still_valid(service, provider, start_dt):
                start_local = pytz.utc.localize(start_dt).astimezone(tz)
                end_local = pytz.utc.localize(end_dt).astimezone(tz) if end_dt else False
                unavailable_lines.append({
                    "line_id": line.id,
                    "service": service.name,
                    "therapist": provider.name,
                    "date": start_local.strftime("%d %b %Y"),
                    "time": "%s - %s" % (
                        start_local.strftime("%I:%M %p"),
                        end_local.strftime("%I:%M %p") if end_local else "",
                    ),
                })

        if unavailable_lines:
            return {
                "valid": False,
                "message": self._format_cart_slot_unavailable_message(unavailable_lines),
                "unavailable_lines": unavailable_lines,
            }
        return {"valid": True, "message": "", "unavailable_lines": []}

    @http.route("/booking/check_slot_in_cart", type="json", auth="public", website=True)
    def check_slot_in_cart(self, service_id, provider_id, start_datetime, **kwargs):
        service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
        provider = request.env["chaitanya.appointment.provider"].sudo().browse(int(provider_id or 0))
        if not service.exists() or not provider.exists() or not start_datetime:
            return {"in_cart": False}
        start_dt = fields.Datetime.from_string(start_datetime)
        end_dt = start_dt + timedelta(minutes=service.duration)
        order = request.website.sale_get_order()
        return {
            "in_cart": self._is_slot_already_in_cart(order, provider, start_dt, end_dt),
            "message": "This time slot is already in your cart.",
        }

    @http.route("/booking/resolve_provider", type="json", auth="public", website=True)
    def resolve_provider(self, service_id, start_datetime, booking_method, provider_id=None, **kwargs):
        try:
            service = request.env["chaitanya.appointment.service"].sudo().browse(int(service_id))
            start_dt = fields.Datetime.from_string(start_datetime)
        except (TypeError, ValueError):
            return {"error": "Invalid input."}

        provider = False
        if provider_id:
            provider = request.env["chaitanya.appointment.provider"].sudo().browse(int(provider_id))

        if not provider and booking_method == "availability":
            provider = self._get_least_busy_provider(service, start_dt, duration)

            if not provider:
                available_for_slot = self._get_providers_for_service_slot(service, start_dt)
                if available_for_slot:
                    return {"error": "This time slot is already in your cart."}

                return {"error": "No therapist is available for this time slot."}

        if not provider:
            return {"error": "Please select a therapist."}

        return {"provider_id": provider.id, "provider_name": provider.name}

    @http.route("/booking/submit", type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def submit_booking(self, **post):
        try:
            service = request.env["chaitanya.appointment.service"].sudo().browse(int(post.get("service_id")))
            provider_id = post.get("provider_id") or post.get("therapist_id")
            provider = False
            if provider_id:
                provider = request.env["chaitanya.appointment.provider"].sudo().browse(int(provider_id))
            start_dt = fields.Datetime.from_string(post.get("start_datetime"))
        except (TypeError, ValueError):
            return self._booking_error("Please choose a valid service and time slot.")

        if not service.exists() or not service.active or not service.website_published:
            return self._booking_error("The selected service is not available.")

        if not provider:
            if post.get("booking_method") == "availability":
                provider = self._get_least_busy_provider(service, start_dt)
                if not provider:
                    return self._booking_error("No therapist is available for this time slot.")
            else:
                return self._booking_error("Please select a therapist.")

        if not provider.exists() or provider not in service.provider_ids.filtered("active"):
            return self._booking_error("The selected therapist is not available for this service.")

        service._ensure_checkout_product()

        product_id = int(post.get("product_id") or service.product_id.id)
        product = request.env["product.product"].sudo().browse(product_id)

        if not product.exists() or product.product_tmpl_id.id != service.product_tmpl_id.id:
            return self._booking_error("Please choose a valid service option.")

        duration = self._get_booking_duration(service, product)
        end_dt = start_dt + timedelta(minutes=duration)

        if not self._is_selected_slot_still_valid(service, provider, start_dt):
            return self._booking_error("The selected slot is no longer available. Please choose another time.")

        order = request.website.sale_get_order(force_create=True)

        if not request.env.user._is_public():
            partner = request.env.user.partner_id.commercial_partner_id
            order.sudo().write({
                "partner_id": partner.id,
                "partner_invoice_id": partner.id,
                "partner_shipping_id": partner.id,
            })

        if self._is_slot_already_in_cart(order, provider, start_dt, end_dt):
            return self._booking_error("This therapist already has this time reserved in your cart.")

        cart_values = order.with_context(chaitanya_force_new_booking_line=True)._cart_update(
            product_id=product.id, add_qty=1,
        )

        line = request.env["sale.order.line"].sudo().browse(cart_values.get("line_id"))
        tz = self._booking_timezone()
        start_local = pytz.utc.localize(start_dt).astimezone(tz)
        end_local = pytz.utc.localize(end_dt).astimezone(tz)

        line.write({
            "name": "%s\nTherapist: %s\nDate: %s\nTime: %s - %s" % (
                service.name, provider.name,
                start_local.strftime("%d %b %Y"),
                start_local.strftime("%I:%M %p"),
                end_local.strftime("%I:%M %p"),
            ),
            "chaitanya_service_id": service.id,
            "chaitanya_provider_id": provider.id,
            "chaitanya_start_datetime": start_dt,
            "chaitanya_end_datetime": end_dt,
            "chaitanya_duration": duration,
            "chaitanya_booking_method": post.get("booking_method") or "availability",
            "chaitanya_is_gift": bool(post.get("is_gift")),
            "chaitanya_gift_delivery_type": post.get("gift_delivery_type") or False,
            "chaitanya_gift_recipient_email": post.get("gift_recipient_email"),
            "chaitanya_gift_recipient_address": post.get("gift_recipient_address"),
            "chaitanya_gift_message": post.get("gift_message"),
            "chaitanya_notes": post.get("notes"),
        })

        return request.redirect("/shop/cart")

    @http.route()
    def checkout(self, **post):
        order = request.website.sale_get_order()
        if order:
            result = self.check_cart_slots()  # ✅ fixed - use self
            if not result.get("valid"):
                request.session["booking_error"] = result.get("message")
                return request.redirect("/shop/cart")
        return super().checkout(**post)

    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        sale_order_id = request.session.get("sale_last_order_id")
        order = request.env["sale.order"].sudo().browse(sale_order_id) if sale_order_id else request.website.sale_get_order()
        if order and order.exists():
            order.sudo()._create_chaitanya_bookings_from_order()
            return request.render("website_sale.confirmation", {
                "order": order,
                "website_sale_order": order,
            })
        return request.redirect("/shop")

    @http.route("/booking/success/<string:booking_reference>", type="http", auth="public", website=True)
    def booking_success(self, booking_reference, **kwargs):
        booking = request.env["chaitanya.appointment.booking"].sudo().search(
            [("name", "=", booking_reference)], limit=1
        )
        if not booking:
            return request.not_found()
        return request.render("chaitanya_booking_flow.booking_success_page", {"booking": booking})

    @http.route("/booking/cart/remove/<int:line_id>", type="http", auth="public", website=True)
    def remove_cart_booking_line(self, line_id, **kwargs):
        order = request.website.sale_get_order()
        if not order:
            return request.redirect("/shop/cart")
        line = request.env["sale.order.line"].sudo().browse(line_id)
        if line.exists() and line.order_id.id == order.id:
            booking = getattr(line, "booking_id", False)
            if booking and booking.exists() and booking.state == "reserved":
                booking.action_cancel()
            order._cart_update(product_id=line.product_id.id, line_id=line.id, set_qty=0)
        return request.redirect("/shop/cart")