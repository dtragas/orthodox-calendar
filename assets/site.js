/* Orthodox Calendar website behaviour: today's calendar leaf, name lookup, list filter, phone download bar. */
(function () {
  var d = document, root = d.documentElement, P = root.getAttribute("data-p") || "";
  var ua = navigator.userAgent || "";
  var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var android = /Android/.test(ua);
  root.classList.add(ios ? "is-ios" : android ? "is-android" : "is-desktop");

  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  var DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var RANK = { greatFeast: "Great Feast", apostle: "Apostle", martyr: "Martyr", venerable: "Venerable", bishop: "Hierarch", holyWoman: "Holy Woman", prophet: "Prophet", general: "Saint" };

  function fold(s) {
    return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function slug(s) {
    return fold(s).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  function el(tag, cls, text) {
    var e = d.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function store(key, val) {
    try {
      if (val === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, val);
    } catch (e) {}
    return null;
  }

  /* ---- today's leaf ---- */
  var leaf = d.querySelector("[data-leaf]");
  if (leaf) {
    var cal = store("oc-cal") === "old" ? "old" : "new";
    var first = true;
    var draw = function () {
      var now = new Date();
      var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      var look = new Date(today);
      if (cal === "old") look.setDate(look.getDate() - 13); // Julian date, valid 1900-2099
      var m = look.getMonth() + 1, day = look.getDate();
      fetch(P + "/assets/days/" + m + ".json").then(function (r) { return r.json(); }).then(function (data) {
        var list = data[day] || [];
        var feast = list.some(function (s) { return s.t === "greatFeast"; });
        leaf.querySelector(".leaf-head .leaf-wd").textContent = DAYS[today.getDay()];
        var num = leaf.querySelector(".leaf-head .leaf-num");
        num.textContent = today.getDate();
        num.className = "leaf-num" + (feast || today.getDay() === 0 ? " red" : "");
        leaf.querySelector(".leaf-head .leaf-my").textContent = MONTHS[today.getMonth()] + " " + today.getFullYear();
        var note = leaf.querySelector(".leaf-note");
        note.hidden = cal !== "old";
        note.textContent = "Old Calendar date: " + MONTHS[m - 1] + " " + day;
        var ul = leaf.querySelector(".leaf-saints");
        ul.textContent = "";
        var names = [];
        list.forEach(function (s) {
          var li = el("li", s.t === "greatFeast" ? "gf" : "");
          var a = el("a", "", s.n);
          a.href = P + "/saints/" + s.s + "/";
          li.appendChild(a);
          li.appendChild(el("span", "", RANK[s.t] || "Saint"));
          ul.appendChild(li);
          (s.m || []).forEach(function (n) { if (names.indexOf(n) < 0) names.push(n); });
        });
        var p = leaf.querySelector(".leaf-names");
        p.textContent = "";
        if (names.length) {
          p.appendChild(el("b", "", "Name days "));
          names.slice(0, 14).forEach(function (n, i) {
            if (i) p.appendChild(d.createTextNode(", "));
            var a = el("a", "", n);
            a.href = P + "/name-days/" + slug(n) + "/";
            p.appendChild(a);
          });
          if (names.length > 14) p.appendChild(d.createTextNode(" and " + (names.length - 14) + " more"));
        }
        var more = leaf.querySelector(".leaf-more");
        more.href = P + "/calendar/" + MONTHS[m - 1].toLowerCase() + "-" + day + "/";
        more.textContent = "Everything for " + MONTHS[m - 1] + " " + day;
        leaf.querySelectorAll(".leaf-cal button").forEach(function (b) {
          b.setAttribute("aria-pressed", b.getAttribute("data-cal") === cal ? "true" : "false");
        });
        if (first) {
          first = false;
          var tear = leaf.querySelector(".leaf-tear");
          if (tear) {
            var y = new Date(today); y.setDate(y.getDate() - 1);
            tear.querySelector(".leaf-wd").textContent = DAYS[y.getDay()];
            tear.querySelector(".leaf-num").textContent = y.getDate();
            tear.querySelector(".leaf-my").textContent = MONTHS[y.getMonth()] + " " + y.getFullYear();
            tear.classList.add("go");
            tear.addEventListener("animationend", function () { tear.remove(); });
          }
        }
      }).catch(function () {});
    };
    leaf.querySelectorAll(".leaf-cal button").forEach(function (b) {
      b.addEventListener("click", function () {
        cal = b.getAttribute("data-cal");
        store("oc-cal", cal);
        draw();
      });
    });
    draw();
  }

  /* ---- name lookup ---- */
  var nf = d.querySelector("[data-namefind]");
  if (nf) {
    var input = nf.querySelector("input"), out = nf.querySelector(".nf-results"), all = null, loading = false;
    var load = function () {
      if (all || loading) return;
      loading = true;
      fetch(P + "/assets/names.json").then(function (r) { return r.json(); }).then(function (a) {
        all = a.map(function (n) { return [n, fold(n)]; });
        show();
      });
    };
    var show = function () {
      var q = fold(input.value.trim());
      out.textContent = "";
      if (!q || !all) { out.hidden = true; return; }
      var starts = [], has = [];
      all.forEach(function (n) {
        var i = n[1].indexOf(q);
        if (i === 0) starts.push(n[0]); else if (i > 0) has.push(n[0]);
      });
      var hits = starts.concat(has).slice(0, 8);
      if (!hits.length) {
        out.appendChild(el("li", "none", "No saint with that name in the calendar. Names without a saint are kept on the Sunday of All Saints."));
      }
      hits.forEach(function (n) {
        var li = el("li"), a = el("a", "", n);
        a.href = P + "/name-days/" + slug(n) + "/";
        li.appendChild(a);
        out.appendChild(li);
      });
      out.hidden = false;
    };
    input.addEventListener("focus", load);
    input.addEventListener("input", function () { load(); show(); });
    nf.addEventListener("submit", function (e) {
      e.preventDefault();
      var a = out.querySelector("a");
      if (a) location.href = a.href;
    });
    d.addEventListener("click", function (e) { if (!nf.contains(e.target)) out.hidden = true; });
  }

  /* ---- filter a long index list ---- */
  var fi = d.querySelector("[data-filter]");
  if (fi) {
    var sections = [].slice.call(d.querySelectorAll(".idx section"));
    var rows = sections.map(function (s) {
      return [].map.call(s.querySelectorAll("li"), function (li) { return [li, fold(li.textContent)]; });
    });
    fi.addEventListener("input", function () {
      var q = fold(fi.value.trim());
      sections.forEach(function (s, i) {
        var any = false;
        rows[i].forEach(function (r) {
          var ok = !q || r[1].indexOf(q) >= 0;
          r[0].hidden = !ok;
          if (ok) any = true;
        });
        s.hidden = !any;
        s.style.contentVisibility = q ? "visible" : "";
      });
    });
  }

  /* ---- download bar on phones ---- */
  var bar = d.querySelector("[data-getbar]");
  if (bar && (ios || android)) {
    var closed = false;
    try { closed = sessionStorage.getItem("oc-bar") === "x"; } catch (e) {}
    if (!closed) {
      bar.hidden = false;
      var onScroll = function () { bar.classList.toggle("on", window.scrollY > 520); };
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
      bar.querySelector("button").addEventListener("click", function () {
        bar.hidden = true;
        try { sessionStorage.setItem("oc-bar", "x"); } catch (e) {}
      });
    }
  }
})();
