/* Orthodox Calendar website analytics: GA4 page views + store_click on App Store / Google Play links. */
(function () {
  var GA_ID = "G-QCQF24MHMN";
  if (/bot|crawl|spider|slurp|lighthouse|headless/i.test(navigator.userAgent)) return;
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag("consent", "default", {
    ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied",
    analytics_storage: "granted"
  });
  gtag("js", new Date());
  gtag("config", GA_ID, { anonymize_ip: true, send_page_view: true });
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
  document.head.appendChild(s);

  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
    if (!a) return;
    var h = a.href || "";
    var store = /apps\.apple\.com/.test(h) ? "app_store" : /play\.google\.com/.test(h) ? "google_play" : "";
    if (!store) return;
    gtag("event", "store_click", { store: store, page_path: location.pathname, link_text: (a.textContent || a.querySelector("img") && a.querySelector("img").alt || "").trim().slice(0, 60) });
  }, true);
})();
