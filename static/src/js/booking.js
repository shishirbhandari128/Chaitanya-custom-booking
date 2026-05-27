/* =========================================================
   Chaitanya Booking - booking.js
   ========================================================= */

// RPC helper
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

// DOM helpers
const getForm = () => document.querySelector(".ch-booking-form");
const getMethod = (form) => form.querySelector("[name='booking_method']").value;

function setMessage(container, message, loading = false) {
    if (!container) return;
    container.innerHTML = `<p class="ch-empty-state${loading ? " is-loading" : ""}">${message}</p>`;
}

function clearSelected(container) {
    if (!container) return;

    container.querySelectorAll(".is-selected").forEach(el => {
        el.classList.remove("is-selected");

        const chooseBtn = el.querySelector(".ch-choose-btn");
        if (chooseBtn) chooseBtn.textContent = "Choose";
    });
}

function scrollToSection(target) {
    if (!target) return;

    const section = target.closest(".ch-panel-section") || target;

    section.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}

function scrollToDateSection(form) {
    scrollToSection(form.querySelector("#chAvailableDateSelect"));
}

function scrollToSlotSection(form) {
    scrollToSection(form.querySelector("#chSlotSection") || form.querySelector("#chSlotCards"));
}

function scrollToTherapistSection(form) {
    scrollToSection(form.querySelector("#chTherapistSection") || form.querySelector("#chTherapistCards"));
}

function resetBookingSelection(form, options = {}) {
    const keepStartDatetime = options.keepStartDatetime || false;

    form.querySelector("#chProviderId").value = "";

    if (!keepStartDatetime) {
        form.querySelector("#chStartDatetime").value = "";
    }

    clearSelected(form.querySelector("#chTherapistCards"));

    if (!keepStartDatetime) {
        setMessage(form.querySelector("#chSlotCards"), "Choose a therapist to see times.");
    }

    const label = form.querySelector(".ch-slots-label");
    if (label) label.textContent = "Available Times";
}

// Slot rendering
function renderSlotCards(form, slots) {
    const slotContainer = form.querySelector("#chSlotCards");
    const startInput = form.querySelector("#chStartDatetime");
    const label = form.querySelector(".ch-slots-label");
    const method = getMethod(form);

    startInput.value = "";

    if (!slots || !slots.length) {
        setMessage(slotContainer, "No available times.");
        return;
    }

    if (label) {
        const today = new Date().toISOString().slice(0, 10);
        const date = form.querySelector("#chBookingDate")?.value
            || form.querySelector("#chAvailableDateSelect")?.value
            || "";

        label.textContent = date === today ? "Available Times Today" : "Available Times";
    }

    slotContainer.innerHTML = "";

    slots.forEach((slot, i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ch-slot-card";
        btn.textContent = slot.provider_count
            ? `${slot.label} (${slot.provider_count})`
            : slot.label;
        btn.style.animationDelay = `${i * 35}ms`;

        btn.addEventListener("click", async () => {
            clearSelected(slotContainer);
            btn.classList.add("is-selected");
            startInput.value = slot.value;

            if (method === "availability") {
                form.querySelector("#chProviderId").value = "";
                await loadTherapistsForSelectedSlot(form, slot.value);
                scrollToTherapistSection(form);
                return;
            }

            const result = await checkSlotInCart(form, slot.value);

            if (result.in_cart) {
                alert(result.message || "This time slot is already in your cart.");
                startInput.value = "";
                btn.classList.remove("is-selected");
            }
        });

        slotContainer.appendChild(btn);
    });
}

// Availability mode: date -> slots
async function loadAvailableTimesForDate(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const date = form.querySelector("#chBookingDate").value;

    form.querySelector("#chProviderId").value = "";
    form.querySelector("#chStartDatetime").value = "";

    clearSelected(form.querySelector("#chTherapistCards"));

    if (!date) {
        setMessage(form.querySelector("#chSlotCards"), "Choose a date to see available times.");
        setMessage(form.querySelector("#chTherapistCards"), "Choose a time slot to see therapists.");
        return;
    }

    setMessage(form.querySelector("#chSlotCards"), "Loading times...", true);
    setMessage(form.querySelector("#chTherapistCards"), "Choose a time slot to see therapists.");

    const slots = await rpc("/booking/get_available_times", {
        service_id: serviceId,
        date,
    });

    renderSlotCards(form, slots);

    if (slots && slots.length) {
        scrollToSlotSection(form);
    }
}

// Availability mode: slot -> therapists
async function loadTherapistsForSelectedSlot(form, startDatetime) {
    const serviceId = form.querySelector("[name='service_id']").value;

    setMessage(form.querySelector("#chTherapistCards"), "Loading therapists...", true);

    const therapists = await rpc("/booking/get_therapists_for_slot", {
        service_id: serviceId,
        start_datetime: startDatetime,
    });

    renderTherapistCards(form, therapists, {keepStartDatetime: true});
}

// Provider dates: therapist-first mode
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

    dates.forEach(date => {
        const opt = document.createElement("option");
        opt.value = date;
        opt.textContent = date;
        dateSelect.appendChild(opt);
    });

    if (preferredDate && dates.includes(preferredDate)) {
        dateSelect.value = preferredDate;
        await loadSlotsForProviderDate(form, providerId, preferredDate);
    }
}

// Therapist-first mode: slots for provider + date
async function loadSlotsForProviderDate(form, providerId, date) {
    if (!providerId || !date) {
        setMessage(form.querySelector("#chSlotCards"), "Choose a therapist and date.");
        return;
    }

    const serviceId = form.querySelector("[name='service_id']").value;

    setMessage(form.querySelector("#chSlotCards"), "Loading times...", true);

    const slots = await rpc("/booking/get_provider_slots", {
        service_id: serviceId,
        provider_id: providerId,
        date,
    });

    renderSlotCards(form, slots);
}

// Therapist card rendering
function renderTherapistCards(form, therapists, options = {}) {
    const container = form.querySelector("#chTherapistCards");
    const method = getMethod(form);

    resetBookingSelection(form, {
        keepStartDatetime: options.keepStartDatetime || false,
    });

    if (!therapists || !therapists.length) {
        const message = method === "availability"
            ? "No therapist is available for this time slot."
            : "No therapist is available.";

        setMessage(container, message);
        return;
    }

    container.innerHTML = "";

    therapists.forEach((t, i) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "ch-therapist-card o_not_editable";
        card.setAttribute("contenteditable", "false");
        card.style.animationDelay = `${i * 60}ms`;

        const nearestHtml = t.nearest_date && t.nearest_time
            ? `<span class="ch-nearest-time">Nearest: ${t.nearest_date} ${t.nearest_time}</span>`
            : "";

        card.innerHTML = `
            <div class="ch-therapist-photo-wrap">
                <img class="ch-therapist-photo" src="${t.image_url}" alt="${t.name}"/>
            </div>
            <div class="ch-therapist-body">
                <p class="ch-therapist-name">${t.name}</p>
                <p class="ch-therapist-spec">${t.specialization || ""}</p>
                ${nearestHtml}
            </div>
            <button type="button" class="ch-choose-btn" tabindex="-1">Choose</button>
        `;

        card.addEventListener("click", async () => {
            const startDatetime = form.querySelector("#chStartDatetime").value;

            if (method === "availability" && !startDatetime) {
                alert("Please choose a time slot first.");
                return;
            }

            form.querySelector("#chProviderId").value = t.id;

            if (method === "availability") {
                const result = await checkSlotInCart(form, startDatetime);

                if (result.in_cart) {
                    alert(result.message || "This time slot is already in your cart.");
                    form.querySelector("#chProviderId").value = "";
                    return;
                }
            }

            clearSelected(container);
            card.classList.add("is-selected");

            const chooseBtn = card.querySelector(".ch-choose-btn");
            if (chooseBtn) chooseBtn.textContent = "Selected";

            if (method === "therapist") {
                await loadProviderDates(form, t.id, t.nearest_date);
                scrollToDateSection(form);
            }
        });

        container.appendChild(card);
    });
}

// Check time slot already in cart
async function checkSlotInCart(form, startDatetime) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const providerId = form.querySelector("#chProviderId").value;

    return rpc("/booking/check_slot_in_cart", {
        service_id: serviceId,
        provider_id: providerId,
        start_datetime: startDatetime,
    });
}

// Therapist-first initial load
async function loadTherapists(form) {
    const serviceId = form.querySelector("[name='service_id']").value;

    setMessage(form.querySelector("#chTherapistCards"), "Loading therapists...", true);

    const therapists = await rpc("/booking/get_therapist_cards", {
        service_id: serviceId,
    });

    renderTherapistCards(form, therapists);
}

// Gift fields toggle
function configureGiftFields(form) {
    const isGift = form.querySelector("#chIsGift").value === "1";
    const giftCard = form.querySelector("#chGiftFields");
    const deliveryType = form.querySelector("#chGiftDeliveryType");
    const emailWrap = form.querySelector("#chGiftEmailWrap");
    const addressWrap = form.querySelector("#chGiftAddressWrap");
    const email = form.querySelector("#chGiftRecipientEmail");
    const address = form.querySelector("#chGiftRecipientAddress");

    if (!giftCard) return;

    giftCard.hidden = !isGift;

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

// Promo code UI
function setupPromoUI(form) {
    const input = form.querySelector("#chPromoDisplay");
    const applyBtn = form.querySelector("#chPromoApplyBtn");
    const note = form.querySelector("#chPromoNote");

    if (!applyBtn) return;

    input.removeAttribute("readonly");

    applyBtn.addEventListener("click", () => {
        const code = input.value.trim();
        if (!code) return;

        note.style.display = "block";
        note.style.color = "var(--ch-accent)";
        note.textContent = `Code "${code}" will be applied at checkout.`;
    });
}

// Init
document.addEventListener("DOMContentLoaded", async () => {
    const form = getForm();
    if (!form) return;

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
    setupPromoUI(form);

    if (method === "therapist") {
        await loadTherapists(form);
    } else {
        setMessage(form.querySelector("#chSlotCards"), "Choose a date to see available times.");
        setMessage(form.querySelector("#chTherapistCards"), "Choose a time slot to see therapists.");
    }

    form.querySelector("#chBookingDate")?.addEventListener("change", () => {
        if (method === "availability") {
            loadAvailableTimesForDate(form);
        }
    });

    form.querySelector("#chAvailableDateSelect")?.addEventListener("change", async () => {
        const providerId = form.querySelector("#chProviderId").value;
        const date = form.querySelector("#chAvailableDateSelect").value;

        await loadSlotsForProviderDate(form, providerId, date);

        if (date) {
            scrollToSlotSection(form);
        }
    });

    form.querySelector("#chGiftDeliveryType")?.addEventListener("change", () => {
        configureGiftFields(form);
    });

    form.addEventListener("submit", event => {
        const providerId = form.querySelector("#chProviderId").value;
        const startDatetime = form.querySelector("#chStartDatetime").value;

        if (!providerId || !startDatetime) {
            event.preventDefault();

            if (!startDatetime) {
                setMessage(form.querySelector("#chSlotCards"), "Please choose a time slot.");
                scrollToSlotSection(form);
            } else {
                setMessage(form.querySelector("#chTherapistCards"), "Please choose a therapist.");
                scrollToTherapistSection(form);
            }
        }
    });
});