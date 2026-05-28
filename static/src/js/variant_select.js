console.log("[Chaitanya] booking variant JS file loaded");

function initChaitanyaBookingVariantLinks() {
    console.log("[Chaitanya] init running");

    function getSelectedProductId() {
        const productInput = document.querySelector("form[action*='/shop/cart/update'] input[name='product_id']")
            || document.querySelector("input[name='product_id']");

        const productId = productInput ? productInput.value : "";

        console.log("[Chaitanya] product input:", productInput);
        console.log("[Chaitanya] selected product.product id:", productId);

        return productId;
    }

    function updateBookingLinks() {
        const productId = getSelectedProductId();

        document.querySelectorAll("#custom_book_now_button, #gift_now_button").forEach(function (link) {
            const url = new URL(link.href, window.location.origin);

            if (productId) {
                url.searchParams.set("product_id", productId);
            }

            link.href = url.pathname + url.search;
            console.log("[Chaitanya] updated link:", link.id, link.href);
        });
    }

    function bindBookingButtons() {
        document.querySelectorAll("#custom_book_now_button, #gift_now_button").forEach(function (link) {
            if (link.dataset.chaitanyaBound === "1") {
                return;
            }

            link.dataset.chaitanyaBound = "1";

            link.addEventListener("click", function (event) {
                updateBookingLinks();
                console.log("[Chaitanya] clicked final href:", link.href);
            });
        });
    }

    bindBookingButtons();
    updateBookingLinks();

    document.addEventListener("change", function (event) {
        console.log("[Chaitanya] change event:", event.target);
        setTimeout(updateBookingLinks, 300);
    });

    document.addEventListener("click", function (event) {
        if (
            event.target.closest(".js_variant_change") ||
            event.target.closest("input[type='radio']") ||
            event.target.closest("select")
        ) {
            console.log("[Chaitanya] variant click:", event.target);
            setTimeout(updateBookingLinks, 300);
        }
    });

    window.addEventListener("hashchange", function () {
        console.log("[Chaitanya] hash changed:", window.location.hash);
        setTimeout(updateBookingLinks, 300);
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChaitanyaBookingVariantLinks);
} else {
    initChaitanyaBookingVariantLinks();
}