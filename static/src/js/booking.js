async function rpc(route, params) {
    const response = await fetch(route, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({jsonrpc: "2.0", method: "call", params, id: Date.now()}),
    });
    const payload = await response.json();
    if (payload.error) {
        throw new Error(payload.error.data?.message || payload.error.message || "RPC error");
    }
    return payload.result;
}

function getBookingForm() {
    return document.querySelector(".ch-booking-form");
}

function option(text, value) {
    const item = document.createElement("option");
    item.textContent = text;
    item.value = value;
    return item;
}

function selectedMethod(form) {
    const checkedMethod = form.querySelector("[name='booking_method']:checked");
    const methodField = form.querySelector("[name='booking_method']");
    return checkedMethod ? checkedMethod.value : methodField.value;
}

function selectedDate(form) {
    if (selectedMethod(form) === "therapist") {
        return form.querySelector("#chAvailableDateSelect").value;
    }
    return form.querySelector("#chBookingDate").value;
}

function setSelectMessage(select, message) {
    select.replaceChildren(option(message, ""));
}

function populateTherapists(form, therapists, emptyMessage) {
    const select = form.querySelector("#chTherapistSelect");
    setSelectMessage(select, therapists.length ? "Choose therapist" : emptyMessage);
    for (const therapist of therapists) {
        const label = therapist.specialization ? `${therapist.name} - ${therapist.specialization}` : therapist.name;
        select.appendChild(option(label, therapist.id));
    }
}

function resetSlots(form, message = "Choose date and therapist first") {
    setSelectMessage(form.querySelector("#chSlotSelect"), message);
}

async function loadAllServiceTherapists(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const therapists = await rpc("/booking/get_service_therapists", {service_id: serviceId});
    populateTherapists(form, therapists, "No therapists are assigned to this service");
}

async function loadAvailableTherapists(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const date = form.querySelector("#chBookingDate").value;
    if (!date) {
        populateTherapists(form, [], "Choose date first");
        resetSlots(form);
        return;
    }
    const therapists = await rpc("/booking/get_available_therapists", {service_id: serviceId, date});
    populateTherapists(form, therapists, "No therapist is available on this date");
    resetSlots(form, therapists.length ? "Choose therapist" : "No slots available");
}

async function loadAvailableDates(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const providerId = form.querySelector("#chTherapistSelect").value;
    const dateSelect = form.querySelector("#chAvailableDateSelect");
    if (!providerId) {
        setSelectMessage(dateSelect, "Choose therapist first");
        resetSlots(form);
        return;
    }
    setSelectMessage(dateSelect, "Loading dates...");
    const dates = await rpc("/booking/get_available_dates", {service_id: serviceId, provider_id: providerId});
    setSelectMessage(dateSelect, dates.length ? "Choose date" : "No available dates");
    for (const date of dates) {
        dateSelect.appendChild(option(date, date));
    }
    resetSlots(form, dates.length ? "Choose date" : "No slots available");
}

async function loadSlots(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const providerId = form.querySelector("#chTherapistSelect").value;
    const date = selectedDate(form);
    const slotSelect = form.querySelector("#chSlotSelect");
    if (!serviceId || !providerId || !date) {
        resetSlots(form);
        return;
    }
    setSelectMessage(slotSelect, "Loading slots...");
    const slots = await rpc("/booking/get_available_slots", {service_id: serviceId, provider_id: providerId, date});
    setSelectMessage(slotSelect, slots.length ? "Choose time slot" : "No slots available");
    for (const slot of slots) {
        slotSelect.appendChild(option(slot.label, slot.value));
    }
}

async function validateVoucher() {
    const form = getBookingForm();
    if (!form) return;
    const serviceId = form.querySelector("[name='service_id']").value;
    const code = form.querySelector("#chVoucherCode").value;
    const priceBox = form.querySelector("#chPriceBox");
    const result = await rpc("/booking/validate_voucher", {service_id: serviceId, code});
    if (!result.valid) {
        priceBox.innerHTML = `<span>${result.message}</span>`;
        return;
    }
    priceBox.innerHTML = `<span>Base: ${result.base_amount}</span><span>Discount: ${result.discount_amount}</span><strong>Total: ${result.final_amount}</strong>`;
}

async function configureMethod(form) {
    const method = selectedMethod(form);
    const dateInputWrap = form.querySelector("#chDateInputWrap");
    const dateSelectWrap = form.querySelector("#chDateSelectWrap");
    const dateInput = form.querySelector("#chBookingDate");
    const dateSelect = form.querySelector("#chAvailableDateSelect");
    dateInput.value = "";
    dateSelect.replaceChildren(option("Choose therapist first", ""));
    resetSlots(form);
    if (method === "therapist") {
        dateInputWrap.hidden = true;
        dateSelectWrap.hidden = false;
        await loadAllServiceTherapists(form);
        return;
    }
    dateInputWrap.hidden = false;
    dateSelectWrap.hidden = true;
    populateTherapists(form, [], "Choose date first");
}

function configureGiftFields(form) {
    const isGift = form.querySelector("#chIsGift").value === "1";
    const giftFields = form.querySelector("#chGiftFields");
    const deliveryType = form.querySelector("#chGiftDeliveryType");
    const emailWrap = form.querySelector("#chGiftEmailWrap");
    const addressWrap = form.querySelector("#chGiftAddressWrap");
    const email = form.querySelector("#chGiftRecipientEmail");
    const address = form.querySelector("#chGiftRecipientAddress");
    giftFields.hidden = !isGift;
    if (!isGift) {
        email.required = false;
        address.required = false;
        return;
    }
    const online = deliveryType.value === "online";
    emailWrap.hidden = !online;
    addressWrap.hidden = online;
    email.required = online;
    address.required = !online;
}

document.addEventListener("DOMContentLoaded", () => {
    const form = getBookingForm();
    if (!form) return;
    configureMethod(form);
    configureGiftFields(form);
    form.querySelectorAll("[name='booking_method']").forEach((radio) => {
        radio.addEventListener("change", () => configureMethod(form));
    });
    form.querySelector("#chBookingDate")?.addEventListener("change", () => loadAvailableTherapists(form));
    form.querySelector("#chAvailableDateSelect")?.addEventListener("change", () => loadSlots(form));
    form.querySelector("#chTherapistSelect")?.addEventListener("change", async () => {
        if (selectedMethod(form) === "therapist") {
            await loadAvailableDates(form);
            return;
        }
        await loadSlots(form);
    });
    form.querySelector("#chGiftDeliveryType")?.addEventListener("change", () => configureGiftFields(form));
    form.querySelector("#chVoucherCode")?.addEventListener("blur", validateVoucher);
});
