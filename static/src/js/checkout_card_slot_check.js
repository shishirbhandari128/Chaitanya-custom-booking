async function chBookingRpc(route, params = {}) {
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

document.addEventListener("click", async event => {
    const checkoutButton = event.target.closest(
        'a[href*="/shop/checkout"], button[name="website_sale_main_button"]'
    );

    if (!checkoutButton) return;

    console.log("Chaitanya checkout slot check running");

    event.preventDefault();
    event.stopPropagation();

    const result = await chBookingRpc("/booking/check_cart_slots");

    console.log("Chaitanya slot check result:", result);

    if (!result.valid) {
        alert(result.message || "Some booking slots are no longer available.");
        return;
    }

    if (checkoutButton.tagName === "A") {
        window.location.href = checkoutButton.href;
    } else {
        checkoutButton.closest("form")?.submit();
    }
});