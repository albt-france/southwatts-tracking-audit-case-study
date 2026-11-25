/* Client M demo shop (fictional client, SIMULATED).
 * Pushes the events of tracking/tracking_plan.md into window.dataLayer. NO tag is loaded: no GTM, no GA4,
 * no pixel, no network call. A "server container preview" shows what the server would forward to Meta CAPI.
 * Bug mode reproduces two planted problems of the case study:
 *   - duplicate purchase: reloading the confirmation page sends purchase again (no localStorage guard);
 *   - Meta double counting: the server copy gets a NEW event_id instead of the browser's one.
 */
(function () {
  "use strict";
  window.dataLayer = window.dataLayer || [];
  window.serverPreview = [];
  function gtag() { window.dataLayer.push(arguments); }

  var CURRENCY = "EUR";
  var PRODUCTS = [
    { item_id: "SKU0001", item_name: "Lamp 0001", price: 49.9, item_category: "Lamp" },
    { item_id: "SKU0002", item_name: "Chair 0002", price: 129.0, item_category: "Chair" },
    { item_id: "SKU0003", item_name: "Desk 0003", price: 249.0, item_category: "Desk" },
    { item_id: "SKU0004", item_name: "Shelf 0004", price: 89.5, item_category: "Shelf" },
    { item_id: "SKU0005", item_name: "Rug 0005", price: 75.0, item_category: "Rug" },
    { item_id: "SKU0006", item_name: "Mirror 0006", price: 59.9, item_category: "Mirror" }
  ];
  var LIST = { item_list_id: "all_products", item_list_name: "All products" };

  function store(kind) { try { return window[kind]; } catch (e) { return null; } }
  function get(kind, key, fallback) {
    try { var v = store(kind).getItem(key); return v === null ? fallback : JSON.parse(v); } catch (e) { return fallback; }
  }
  function set(kind, key, value) { try { store(kind).setItem(key, JSON.stringify(value)); } catch (e) { /* storage blocked */ } }

  function bugMode() { return get("localStorage", "cm_bug_mode", false) === true; }
  function cart() { return get("sessionStorage", "cm_cart", []); }
  function saveCart(c) { set("sessionStorage", "cm_cart", c); renderCartLink(); }
  function eventId() {
    var b = new Uint8Array(8); window.crypto.getRandomValues(b);
    return "evt_" + Array.prototype.map.call(b, function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
  }
  function money(n) { return Math.round(n * 100) / 100; }
  function item(p, qty, extra) {
    var it = { item_id: p.item_id, item_name: p.item_name, price: p.price, quantity: qty, item_category: p.item_category };
    for (var k in (extra || {})) { it[k] = extra[k]; }
    return it;
  }
  function cartItems() {
    return cart().map(function (l) { return item(PRODUCTS.filter(function (p) { return p.item_id === l.id; })[0], l.qty); });
  }
  function total(items) { return money(items.reduce(function (s, i) { return s + i.price * i.quantity; }, 0)); }

  // ---- push helpers ------------------------------------------------------
  function pushEcommerce(event, ecommerce, withId) {
    window.dataLayer.push({ ecommerce: null });                    // clear the previous ecommerce object
    var msg = { event: event, ecommerce: ecommerce };
    if (withId) { msg.event_id = eventId(); }
    window.dataLayer.push(msg);
    if (withId) { forwardToServer(msg); }
    log(msg);
    return msg;
  }
  var META_NAMES = { view_item: "ViewContent", add_to_cart: "AddToCart", begin_checkout: "InitiateCheckout",
                     add_payment_info: "AddPaymentInfo", purchase: "Purchase" };
  function forwardToServer(msg) {
    // the server container reuses the browser event_id; in bug mode it generates a new one (planted event 2)
    var id = (bugMode() && msg.event === "purchase") ? eventId().replace("evt_", "srv_") : msg.event_id;
    var copy = { destination: "meta_capi", event_name: META_NAMES[msg.event], event_id: id, browser_event_id: msg.event_id };
    window.serverPreview.push(copy);
    logServer(copy);
  }

  // ---- consent -------------------------------------------------------------
  gtag("consent", "default", { ad_storage: "denied", analytics_storage: "denied", ad_user_data: "denied",
                               ad_personalization: "denied", wait_for_update: 500 });
  log({ "consent": "default", ad_storage: "denied", analytics_storage: "denied", ad_user_data: "denied", ad_personalization: "denied" });
  function consentUpdate(state) {
    var v = { ad_storage: state, analytics_storage: state, ad_user_data: state, ad_personalization: state };
    gtag("consent", "update", v);
    set("localStorage", "cm_consent", state);
    log({ consent: "update", ad_storage: state, analytics_storage: state });
    document.getElementById("consent").hidden = true;
  }
  var saved = get("localStorage", "cm_consent", null);
  if (saved) { gtag("consent", "update", { ad_storage: saved, analytics_storage: saved, ad_user_data: saved, ad_personalization: saved }); }
  else { document.getElementById("consent").hidden = false; }
  document.getElementById("consent-accept").addEventListener("click", function () { consentUpdate("granted"); });
  document.getElementById("consent-deny").addEventListener("click", function () { consentUpdate("denied"); });

  // ---- logs ----------------------------------------------------------------
  function li(listId, obj, warn) {
    var el = document.createElement("li");
    el.textContent = JSON.stringify(obj, null, 1);
    if (warn) { el.className = "warn"; }
    document.getElementById(listId).appendChild(el);
    el.scrollIntoView({ block: "nearest" });
  }
  function log(obj) { li("dl-log", obj, false); }
  function logServer(copy) { li("srv-log", copy, copy.event_id !== copy.browser_event_id); }
  document.getElementById("clear-log").addEventListener("click", function () {
    document.getElementById("dl-log").innerHTML = ""; document.getElementById("srv-log").innerHTML = "";
  });

  var toggle = document.getElementById("bug-toggle");
  toggle.checked = bugMode();
  toggle.addEventListener("change", function () { set("localStorage", "cm_bug_mode", toggle.checked); });

  // ---- views ---------------------------------------------------------------
  var view = document.getElementById("view");
  function renderCartLink() {
    var n = cart().reduce(function (s, l) { return s + l.qty; }, 0);
    document.getElementById("cart-link").textContent = "Cart (" + n + ")";
  }
  function h(tag, attrs, text) {
    var el = document.createElement(tag);
    for (var k in (attrs || {})) { el.setAttribute(k, attrs[k]); }
    if (text !== undefined) { el.textContent = text; }
    return el;
  }
  function viewList() {
    view.innerHTML = "<h1>All products</h1>";
    var grid = h("div", { "class": "grid" });
    PRODUCTS.forEach(function (p, i) {
      var c = h("div", { "class": "card" });
      c.appendChild(h("div", { "class": "thumb" }));
      c.appendChild(h("div", {}, p.item_name));
      c.appendChild(h("div", { "class": "price" }, p.price.toFixed(2) + " " + CURRENCY));
      var a = h("a", { href: "#/product/" + p.item_id, "data-testid": "open-" + p.item_id }, "View");
      c.appendChild(a);
      grid.appendChild(c);
    });
    view.appendChild(grid);
    pushEcommerce("view_item_list", { item_list_id: LIST.item_list_id, item_list_name: LIST.item_list_name,
      items: PRODUCTS.map(function (p) { return item(p, 1, { item_list_name: LIST.item_list_name }); }) }, false);
  }
  function viewProduct(id) {
    var p = PRODUCTS.filter(function (x) { return x.item_id === id; })[0];
    if (!p) { location.hash = "#/list"; return; }
    view.innerHTML = "";
    view.appendChild(h("h1", {}, p.item_name));
    view.appendChild(h("div", { "class": "thumb" }));
    view.appendChild(h("p", { "class": "price" }, p.price.toFixed(2) + " " + CURRENCY));
    var b = h("button", { type: "button", "data-testid": "add-to-cart" }, "Add to cart");
    b.addEventListener("click", function () {
      var c = cart(); var line = c.filter(function (l) { return l.id === id; })[0];
      if (line) { line.qty += 1; } else { c.push({ id: id, qty: 1 }); }
      saveCart(c);
      pushEcommerce("add_to_cart", { currency: CURRENCY, value: p.price, items: [item(p, 1)] }, true);
    });
    view.appendChild(b);
    pushEcommerce("view_item", { currency: CURRENCY, value: p.price, items: [item(p, 1)] }, true);
  }
  function viewCart() {
    var items = cartItems();
    view.innerHTML = "<h1>Cart</h1>";
    if (!items.length) { view.appendChild(h("p", {}, "Your cart is empty.")); return; }
    var t = h("table");
    items.forEach(function (i) { var tr = h("tr"); tr.appendChild(h("td", {}, i.item_name + " x " + i.quantity)); tr.appendChild(h("td", {}, money(i.price * i.quantity).toFixed(2) + " " + CURRENCY)); t.appendChild(tr); });
    view.appendChild(t);
    view.appendChild(h("p", { "class": "price" }, "Total " + total(items).toFixed(2) + " " + CURRENCY));
    var a = h("a", { href: "#/checkout", "data-testid": "go-checkout" }, "Checkout");
    view.appendChild(a);
  }
  function viewCheckout() {
    var items = cartItems();
    if (!items.length) { location.hash = "#/cart"; return; }
    view.innerHTML = "<h1>Checkout</h1><p>Delivery details are not collected in this demo.</p>";
    ["card", "paypal", "bank_transfer"].forEach(function (pt) {
      var b = h("button", { type: "button", "data-testid": "pay-" + pt, "class": "ghost" }, "Pay by " + pt.replace("_", " "));
      b.addEventListener("click", function () {
        pushEcommerce("add_payment_info", { currency: CURRENCY, value: total(items), payment_type: pt, items: items }, true);
        var place = h("button", { type: "button", "data-testid": "place-order" }, "Place order");
        place.addEventListener("click", function () {
          var tx = "CMFR" + String(Math.floor(Math.random() * 1e7)).padStart(7, "0");
          set("sessionStorage", "cm_order_" + tx, { items: items, value: total(items) });
          saveCart([]);
          location.hash = "#/confirmation/" + tx;
        });
        view.appendChild(place);
      });
      view.appendChild(b);
    });
    pushEcommerce("begin_checkout", { currency: CURRENCY, value: total(items), items: items }, true);
  }
  function viewConfirmation(tx) {
    var order = get("sessionStorage", "cm_order_" + tx, null);
    view.innerHTML = "";
    view.appendChild(h("h1", {}, "Thank you"));
    view.appendChild(h("p", { "data-testid": "order-id" }, "Order " + tx));
    if (!order) { return; }
    var sent = get("localStorage", "cm_sent_tx", []);
    if (sent.indexOf(tx) !== -1 && !bugMode()) {          // guard: purchase once per transaction_id
      log({ info: "purchase already sent for " + tx + ": skipped (reload guard)" });
      return;
    }
    pushEcommerce("purchase", { transaction_id: tx, value: order.value, currency: CURRENCY, tax: money(order.value * 0.2 / 1.2),
                                shipping: 0, items: order.items }, true);
    if (sent.indexOf(tx) === -1) { sent.push(tx); set("localStorage", "cm_sent_tx", sent); }
  }
  function route() {
    var parts = (location.hash || "#/list").slice(2).split("/");
    if (parts[0] === "product") { viewProduct(parts[1]); }
    else if (parts[0] === "cart") { viewCart(); }
    else if (parts[0] === "checkout") { viewCheckout(); }
    else if (parts[0] === "confirmation") { viewConfirmation(parts[1]); }
    else { viewList(); }
  }
  window.addEventListener("hashchange", route);
  renderCartLink();
  route();
})();
