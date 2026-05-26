/* =========================================================
   Chaitanya Booking — booking.js
   ========================================================= */

// ── RPC helper ────────────────────────────────────────────
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

// ── DOM helpers ───────────────────────────────────────────
const getForm   = ()  => document.querySelector(".ch-booking-form");
const getMethod = (f) => f.querySelector("[name='booking_method']").value;

function setMessage(container, message, loading = false) {
    container.innerHTML = `<p class="ch-empty-state${loading ? " is-loading" : ""}">${message}</p>`;
}

function clearSelected(container) {
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
    scrollToSection(form.querySelector("#chSlotCards"));
}

function resetBookingSelection(form) {
    form.querySelector("#chProviderId").value    = "";
    form.querySelector("#chStartDatetime").value = "";
    setMessage(form.querySelector("#chSlotCards"), "Choose a therapist to see times.");

    const label = form.querySelector(".ch-slots-label");
    if (label) label.textContent = "Available Times";
}

// ── Slot rendering ────────────────────────────────────────
function renderSlotCards(form, slots) {
    const slotContainer = form.querySelector("#chSlotCards");
    const startInput    = form.querySelector("#chStartDatetime");
    const label         = form.querySelector(".ch-slots-label");

    startInput.value = "";

    if (!slots || !slots.length) {
        setMessage(slotContainer, "No available times.");
        return;
    }

    if (label) {
        const today = new Date().toISOString().slice(0, 10);
        const date  = form.querySelector("#chBookingDate")?.value
                   || form.querySelector("#chAvailableDateSelect")?.value
                   || "";
        label.textContent = date === today ? "Available Times Today" : "Available Times";
    }

    slotContainer.innerHTML = "";

    slots.forEach((slot, i) => {
        const btn = document.createElement("button");
        btn.type  = "button";
        btn.className = "ch-slot-card";
        btn.textContent = slot.label;
        btn.style.animationDelay = `${i * 35}ms`;

        btn.addEventListener("click", async () => {
            const result = await checkSlotInCart(form, slot.value);

            if (result.in_cart) {
                alert(result.message || "This time slot is already in your cart.");
                return;
            }

            startInput.value = slot.value;
            clearSelected(slotContainer);
            btn.classList.add("is-selected");
        });
        slotContainer.appendChild(btn);
    });
}






// ── Provider dates (therapist-first mode) ─────────────────
async function loadProviderDates(form, providerId, preferredDate) {
    const serviceId  = form.querySelector("[name='service_id']").value;
    const dateSelect = form.querySelector("#chAvailableDateSelect");

    dateSelect.innerHTML = `<option value="">Loading dates…</option>`;

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
        opt.value       = date;
        opt.textContent = date;
        dateSelect.appendChild(opt);
    });

    if (preferredDate && dates.includes(preferredDate)) {
        dateSelect.value = preferredDate;
        await loadSlotsForProviderDate(form, providerId, preferredDate);
    }
}

// ── Slots for provider + date ─────────────────────────────
async function loadSlotsForProviderDate(form, providerId, date) {
    if (!providerId || !date) {
        setMessage(form.querySelector("#chSlotCards"), "Choose a therapist and date.");
        return;
    }

    const serviceId = form.querySelector("[name='service_id']").value;

    setMessage(form.querySelector("#chSlotCards"), "Loading times…", true);

    const slots = await rpc("/booking/get_provider_slots", {
        service_id: serviceId,
        provider_id: providerId,
        date,
    });

    renderSlotCards(form, slots);
}

// ── Therapist card rendering ──────────────────────────────
function renderTherapistCards(form, therapists) {
    const container = form.querySelector("#chTherapistCards");
    const method    = getMethod(form);

    resetBookingSelection(form);

    if (!therapists || !therapists.length) {
        const date  = form.querySelector("#chBookingDate")?.value || "";
        const today = new Date().toISOString().slice(0, 10);
        setMessage(container, date === today ? "No therapist available today." : "No therapist is available.");
        return;
    }

    container.innerHTML = "";

    therapists.forEach((t, i) => {
        const card = document.createElement("button");
        card.type  = "button";
        card.className = "ch-therapist-card o_not_editable";
        card.setAttribute("contenteditable", "false");
        card.style.animationDelay = `${i * 60}ms`;

        card.innerHTML = `
            <div class="ch-therapist-photo-wrap">
                <img class="ch-therapist-photo" src="${t.image_url}" alt="${t.name}"/>
            </div>
            <div class="ch-therapist-body">
                <p class="ch-therapist-name">${t.name}</p>
                <p class="ch-therapist-spec">${t.specialization || ""}</p>
                <span class="ch-nearest-time">Nearest: ${t.nearest_date} ${t.nearest_time}</span>
            </div>
            <button type="button" class="ch-choose-btn" tabindex="-1">Choose</button>
        `;

        card.addEventListener("click", async () => {
            form.querySelector("#chProviderId").value = t.id;

            clearSelected(container);
            card.classList.add("is-selected");

            const chooseBtn = card.querySelector(".ch-choose-btn");
            if (chooseBtn) chooseBtn.textContent = "Selected ✓";

            if (method === "availability") {
                renderSlotCards(form, t.slots || []);
                scrollToSlotSection(form);
            } else {
                await loadProviderDates(form, t.id, t.nearest_date);
                scrollToDateSection(form);
            }
        });

        container.appendChild(card);
    });
}
// check time slot already in cart
async function checkSlotInCart(form, startDatetime) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const providerId = form.querySelector("#chProviderId").value;

    return rpc("/booking/check_slot_in_cart", {
        service_id: serviceId,
        provider_id: providerId,
        start_datetime: startDatetime,
    });
}

// ── Load therapists from server ───────────────────────────
async function loadTherapists(form) {
    const serviceId = form.querySelector("[name='service_id']").value;
    const method    = getMethod(form);

    setMessage(form.querySelector("#chTherapistCards"), "Loading therapists…", true);

    const params = {service_id: serviceId};

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

// ── Gift fields toggle ────────────────────────────────────
function configureGiftFields(form) {
    const isGift       = form.querySelector("#chIsGift").value === "1";
    const giftCard     = form.querySelector("#chGiftFields");
    const deliveryType = form.querySelector("#chGiftDeliveryType");
    const emailWrap    = form.querySelector("#chGiftEmailWrap");
    const addressWrap  = form.querySelector("#chGiftAddressWrap");
    const email        = form.querySelector("#chGiftRecipientEmail");
    const address      = form.querySelector("#chGiftRecipientAddress");

    if (!giftCard) return;

    giftCard.hidden = !isGift;

    if (!isGift) {
        email.required   = false;
        address.required = false;
        return;
    }

    const online = deliveryType.value === "online";

    emailWrap.hidden   = !online;
    addressWrap.hidden = online;
    email.required     = online;
    address.required   = !online;
}

// ── Promo code UI (informational — actual apply on /shop/cart) ──
function setupPromoUI(form) {
    const input    = form.querySelector("#chPromoDisplay");
    const applyBtn = form.querySelector("#chPromoApplyBtn");
    const note     = form.querySelector("#chPromoNote");

    if (!applyBtn) return;

    input.removeAttribute("readonly");

    applyBtn.addEventListener("click", () => {
        const code = input.value.trim();
        if (!code) return;

        note.style.display = "block";
        note.style.color   = "var(--ch-accent)";
        note.textContent   = `Code "${code}" will be applied at checkout.`;
    });
}

// ── Init ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    const form = getForm();
    if (!form) return;

    const method         = getMethod(form);
    const dateInputWrap  = form.querySelector("#chDateInputWrap");
    const dateSelectWrap = form.querySelector("#chDateSelectWrap");

    if (method === "therapist") {
        dateInputWrap.hidden  = true;
        dateSelectWrap.hidden = false;
    } else {
        dateInputWrap.hidden  = false;
        dateSelectWrap.hidden = true;
    }

    configureGiftFields(form);
    setupPromoUI(form);

    if (method === "therapist") {
        await loadTherapists(form);
    } else {
        setMessage(form.querySelector("#chTherapistCards"), "Choose a date to see therapists.");
    }

    form.querySelector("#chBookingDate")?.addEventListener("change", () => {
        loadTherapists(form);
    });

    form.querySelector("#chAvailableDateSelect")?.addEventListener("change", async () => {
        const providerId = form.querySelector("#chProviderId").value;
        const date       = form.querySelector("#chAvailableDateSelect").value;

        await loadSlotsForProviderDate(form, providerId, date);

        if (date) {
            scrollToSlotSection(form);
        }
    });

    form.querySelector("#chGiftDeliveryType")?.addEventListener("change", () => {
        configureGiftFields(form);
    });

    form.addEventListener("submit", event => {
        const providerId    = form.querySelector("#chProviderId").value;
        const startDatetime = form.querySelector("#chStartDatetime").value;

        if (!providerId || !startDatetime) {
            event.preventDefault();
            setMessage(form.querySelector("#chSlotCards"), "⚠ Please choose a therapist and a time slot.");
        }
    });
});