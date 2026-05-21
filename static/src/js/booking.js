async function rpc(route, params) {
    const response = await fetch(route, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params,
            id: Date.now(),
        }),
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

function getMethod(form) {
    return form.querySelector("[name='booking_method']").value;
}

function setMessage(container, message) {
    container.innerHTML = `<p class="ch-empty-state">${message}</p>`;
}

function clearSelection(container) {
    container.querySelectorAll(".is-selected").forEach((el) => {
        el.classList.remove("is-selected");
    });
}

function setSelected(container, element) {
    clearSelection(container);
    element.classList.add("is-selected");
}

function resetBookingSelection(form) {
    form.querySelector("#chProviderId").value = "";
    form.querySelector("#chStartDatetime").value = "";
    setMessage(form.querySelector("#chSlotCards"), "Choose a therapist to see times.");
}

function renderSlotCards(form, slots) {
    const slotContainer = form.querySelector("#chSlotCards");
    const startInput = form.querySelector("#chStartDatetime");

    startInput.value = "";

    if (!slots || !slots.length) {
        setMessage(slotContainer, "No available times.");
        return;
    }

    slotContainer.innerHTML = "";

    slots.forEach((slot) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ch-slot-card";
        button.textContent = slot.label;

        button.addEventListener("click", () => {
            startInput.value = slot.value;
            setSelected(slotContainer, button);
        });

        slotContainer.appendChild(button);
    });
}

async function loadSlotsForProviderDate(form, providerId, date) {
    if (!providerId || !date) {
        setMessage(form.querySelector("#chSlotCards"), "Choose a therapist and date.");
        return;
    }

    const serviceId = form.querySelector("[name='service_id']").value;

    setMessage(form.querySelector("#chSlotCards"), "Loading times...");

    const slots = await rpc("/booking/get_provider_slots", {
        service_id: serviceId,
        provider_id: providerId,
        date: date,
    });

    renderSlotCards(form, slots);
}

async function loadProviderDates(form, providerId, preferredDate) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const dateSelect = form.querySelector("#chAvailableDateSelect");

    dateSelect.innerHTML = `<option value="">Loading dates...</option>`;

    const dates = await rpc("/booking/get_provider_dates", {
        service_id: serviceId,
        provider_id: providerId,
    });

    if (!dates.length) {
        dateSelect.innerHTML = `<option value="">No available dates</option>`;
        setMessage(form.querySelector("#chSlotCards"), "No available dates.");
        return;
    }

    dateSelect.innerHTML = `<option value="">Choose date</option>`;

    dates.forEach((date) => {
        const option = document.createElement("option");
        option.value = date;
        option.textContent = date;
        dateSelect.appendChild(option);
    });

    if (preferredDate && dates.includes(preferredDate)) {
        dateSelect.value = preferredDate;
        await loadSlotsForProviderDate(form, providerId, preferredDate);
    }
}

function renderTherapistCards(form, therapists) {
    const therapistContainer = form.querySelector("#chTherapistCards");
    const method = getMethod(form);

    resetBookingSelection(form);

    if (!therapists || !therapists.length) {
        const selectedDate = form.querySelector("#chBookingDate")?.value;
        const today = new Date().toISOString().slice(0, 10);

        if (selectedDate === today) {
            setMessage(therapistContainer, "No therapist available today.");
        } else {
            setMessage(therapistContainer, "No therapist is available.");
        }
        return;
    }

    therapistContainer.innerHTML = "";

    therapists.forEach((therapist) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "ch-therapist-card";

        card.innerHTML = `
            <img class="ch-therapist-photo" src="${therapist.image_url}" alt="">
            <span class="ch-therapist-info">
                <strong>${therapist.name}</strong>
                <small>${therapist.specialization || ""}</small>
                <span class="ch-nearest-time">
                    Nearest: ${therapist.nearest_date} ${therapist.nearest_time}
                </span>
            </span>
        `;

        card.addEventListener("click", async () => {
            form.querySelector("#chProviderId").value = therapist.id;
            setSelected(therapistContainer, card);

            if (method === "availability") {
                renderSlotCards(form, therapist.slots || []);
            } else {
                await loadProviderDates(form, therapist.id, therapist.nearest_date);
            }
        });

        therapistContainer.appendChild(card);
    });
}

async function loadTherapists(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const method = getMethod(form);

    setMessage(form.querySelector("#chTherapistCards"), "Loading therapists...");

    let params = {service_id: serviceId};

    if (method === "availability") {
        const date = form.querySelector("#chBookingDate").value;

        if (!date) {
            setMessage(form.querySelector("#chTherapistCards"), "Choose a date to see therapists.");
            setMessage(form.querySelector("#chSlotCards"), "Choose a therapist to see times.");
            return;
        }

        params.date = date;
    }

    const therapists = await rpc("/booking/get_therapist_cards", params);
    renderTherapistCards(form, therapists);
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

document.addEventListener("DOMContentLoaded", async () => {
    const form = getBookingForm();

    if (!form) {
        return;
    }

    const method = getMethod(form);
    const dateInputWrap = form.querySelector("#chDateInputWrap");
    const dateSelectWrap = form.querySelector("#chDateSelectWrap");

    if (method === "therapist") {
        dateInputWrap.hidden = true;
        dateSelectWrap.hidden = false;
    } else {
        dateInputWrap.hidden = false;
        dateSelectWrap.hidden = true;
    }

    configureGiftFields(form);

    if (method === "therapist") {
        await loadTherapists(form);
    } else {
        setMessage(form.querySelector("#chTherapistCards"), "Choose a date to see therapists.");
    }

    form.querySelector("#chBookingDate")?.addEventListener("change", () => {
        loadTherapists(form);
    });

    form.querySelector("#chAvailableDateSelect")?.addEventListener("change", () => {
        const providerId = form.querySelector("#chProviderId").value;
        const date = form.querySelector("#chAvailableDateSelect").value;
        loadSlotsForProviderDate(form, providerId, date);
    });

    form.querySelector("#chGiftDeliveryType")?.addEventListener("change", () => {
        configureGiftFields(form);
    });

    form.addEventListener("submit", (event) => {
        const providerId = form.querySelector("#chProviderId").value;
        const startDatetime = form.querySelector("#chStartDatetime").value;

        if (!providerId || !startDatetime) {
            event.preventDefault();
            setMessage(form.querySelector("#chSlotCards"), "Please choose a therapist and time.");
        }
    });
});