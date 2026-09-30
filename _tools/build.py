#!/usr/bin/env python3
"""Static site generator for the Orthodox Calendar website.

Reads saint/saints/<month>.json (the same export the /saint deep-link page uses),
_tools/icons.json and _tools/guides/*.html, and writes every public page:

  index.html, today/, calendar/ (12 months + 366 days), name-days/ (one page per
  name), saints/ (one page per saint), guides/, sitemap.xml, 404.html,
  assets/days/<month>.json and assets/names.json (for the live "today" leaf).

Run:  python3 _tools/build.py
The address of the site is set by ORIGIN and PREFIX below.
Hand-written files it never touches: get/, saint/, privacy-policy.html, support.html, CNAME, .well-known/,
assets/site.css, assets/site.js.
"""
import datetime, glob, hashlib, html, json, os, re, shutil, unicodedata

ORIGIN = "https://orthodoxcalendar.net"
PREFIX = ""                            # the site sits at the root of its own domain
SITE = "Orthodox Calendar"
IOS_URL = "https://apps.apple.com/us/app/orthodox-calendar-name-days/id6783400246"
PLAY_URL = ("https://play.google.com/store/apps/details?id=com.twopensmedia.orthodoxcalendar"
            "&referrer=utm_source%3Dwebsite%26utm_medium%3Dbadge")
APP_ID = "6783400246"
PUBLISHED = "2026-09-30"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today()
P = PREFIX
e = html.escape

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MDAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
RANK = {"greatFeast": "Great Feast", "apostle": "Apostle", "martyr": "Martyr", "venerable": "Venerable",
        "bishop": "Hierarch", "holyWoman": "Holy Woman", "prophet": "Prophet", "general": "Saint"}

# The feast most Greek families keep when a name has several. Applied only when the
# date really is one of that name's feasts in the data.
PRIMARY = {}
for names, md in [
    ("John Ioannis Giannis Yiannis Yannis Ioanna Joanna Gianna Yianna", (1, 7)),
    ("Maria Mary Panagiotis Panagiota Despina Marios", (8, 15)),
    ("George Georgios Giorgos Yiorgos Georgia", (4, 23)),
    ("Anna", (12, 9)),
    ("Michael Michail Michalis Gabriel Angelos Angeliki", (11, 8)),
    ("Nicholas Nikolaos Nikos Nikoleta Nikoletta", (12, 6)),
    ("Dimitrios Dimitris Demetrios Dimitra", (10, 26)),
    ("Konstantinos Constantine Kostas Eleni Helen", (5, 21)),
    ("Andrew Andreas", (11, 30)),
    ("Peter Petros Paul Pavlos", (6, 29)),
    ("Athanasios Thanasis Athanasia", (1, 18)),
    ("Anthony Antonios Antonis Antonia", (1, 17)),
    ("Basil Vasilios Vasilis Vasiliki", (1, 1)),
    ("Stephen Stefanos Stephanos Stefania", (12, 27)),
    ("Katerina Aikaterini Catherine Katherine", (11, 25)),
    ("Spyridon Spyros", (12, 12)),
    ("Alexander Alexandros Alexandra", (8, 30)),
    ("Elias Ilias", (7, 20)),
    ("Gregory Grigorios Grigoris", (1, 25)),
    ("Mark Markos", (4, 25)),
    ("Luke Loukas", (10, 18)),
    ("Irene Eirini Irini", (5, 5)),
    ("Sophia Sofia", (9, 17)),
    ("Barbara Varvara", (12, 4)),
    ("Marina", (7, 17)),
    ("Paraskevi", (7, 26)),
    ("Kyriaki", (7, 7)),
    ("Anastasia", (12, 22)),
    ("Stavros Stavroula", (9, 14)),
    ("Charalambos Haralambos", (2, 10)),
    ("Eleftherios Eleftheria", (12, 15)),
    ("Savvas", (12, 5)),
    ("Nektarios", (11, 9)),
    ("Christos", (12, 25)),
    ("Apostolos Apostolis Tolis", (6, 30)),
    ("Emmanuel Emmanouil Manolis Manos", (12, 26)),
    ("Panos Panayiotis Panagiota Panayiota", (8, 15)),
]:
    for n in names.split():
        PRIMARY[n] = md
POPULAR = ["George", "Maria", "John", "Dimitrios", "Eleni", "Nicholas", "Katerina", "Konstantinos",
           "Anna", "Michael", "Georgia", "Vasiliki", "Panagiotis", "Dimitra", "Sophia", "Irene", "Spyridon",
           "Despina", "Christos"]


# ---------------------------------------------------------------- helpers
def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


def fmt(m, d):
    return f"{MONTHS[m - 1]} {d}"


def day_slug(m, d):
    return f"{MONTHS[m - 1].lower()}-{d}"


def day_url(m, d):
    return f"{P}/calendar/{day_slug(m, d)}/"


def old_civil(m, d):
    """Civil (Gregorian) date on which Old Calendar churches keep Julian date m/d, 1900-2099."""
    base = datetime.date(2000, 2, 29) if (m, d) == (2, 29) else datetime.date(2001, m, d)
    r = base + datetime.timedelta(days=13)
    return r.month, r.day


def old_note(m, d):
    om, od = old_civil(m, d)
    s = fmt(om, od)
    if m == 2 and 17 <= d <= 28:
        s += " (a day earlier in leap years)"
    return s


def poss(name):
    return name + "’s"


def first_para(bio):
    return bio.split("\n\n")[0].strip()


def paras(bio):
    return "".join(f"<p>{e(p.strip())}</p>" for p in bio.split("\n\n") if p.strip())


def join_names(items, limit=None):
    items = list(items)
    more = 0
    if limit and len(items) > limit:
        more = len(items) - limit
        items = items[:limit]
    s = ", ".join(items)
    if more:
        s += f" and {more} more"
    return s


def trim(text, n=158):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n:
        return text
    cut = text[:n - 1]
    return cut[:cut.rfind(" ")].rstrip(",;:") + "…"


def asset_v(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


# ---------------------------------------------------------------- data
DAYS = {}                                   # (m, d) -> [saint, ...]
for f in glob.glob(os.path.join(ROOT, "saint/saints/*.json")):
    for key, lst in json.load(open(f, encoding="utf-8")).items():
        m, d = (int(x) for x in key.split("-"))
        for s in lst:
            s["m"], s["d"] = m, d
            assert re.fullmatch(r"[a-z0-9-]+", s["slug"]), s["slug"]
        DAYS[(m, d)] = lst
ORDER = sorted(DAYS)
ICONS = json.load(open(os.path.join(ROOT, "_tools/icons.json"), encoding="utf-8"))

SAINTS = {}                                 # slug -> [entry, ...] (a saint can have two feasts)
for md in ORDER:
    for s in DAYS[md]:
        SAINTS.setdefault(s["slug"], []).append(s)

def all_names(s):
    """Names that celebrate with this saint. The apps also match a saint's own one-word
    name (Tatiana, Glykeria), so it counts here even when the lists leave it out."""
    names = s["masc"] + s["fem"]
    if " " not in s["name"] and s["type"] != "greatFeast" and s["name"] not in names:
        names = [s["name"]] + names
    return names


NAMES = {}                                  # name slug -> {"name": display, "feasts": [saint, ...]}
for md in ORDER:
    for s in DAYS[md]:
        for n in all_names(s):
            rec = NAMES.setdefault(slugify(n), {"name": n, "feasts": []})
            if s not in rec["feasts"]:
                rec["feasts"].append(s)


def name_link(n):
    return f'<a href="{P}/name-days/{slugify(n)}/">{e(n)}</a>'


def saint_url(s):
    return f"{P}/saints/{s['slug']}/"


def is_gf(md):
    return any(s["type"] == "greatFeast" for s in DAYS[md])


EVENT_WORDS = {"Circumcision", "Three", "Presentation", "Finding", "Annunciation", "Synaxis", "Third", "Nativity",
               "Transfiguration", "Dormition", "Translation", "Beheading", "Beginning", "Miracle", "Exaltation",
               "Conception", "Protection", "Entry", "Second", "First", "Uncovering", "Deposition", "Placing", "Repose"}


def the(s):
    """'the ' before feasts named for an event, so 'the feast of the Dormition' reads right."""
    return "the " if s["name"].split()[0] in EVENT_WORDS else ""


def primary_feast(rec):
    md = PRIMARY.get(rec["name"])
    if md:
        for s in rec["feasts"]:
            if (s["m"], s["d"]) == md:
                return s
    return None


# ---------------------------------------------------------------- page shell
CSS_V = asset_v("assets/site.css")
JS_V = asset_v("assets/site.js")
GA_V = asset_v("assets/analytics.js")
CROSS = ('<svg width="18" height="25" viewBox="0 0 22 30" aria-hidden="true"><g fill="#c8a84c">'
         '<rect x="9.5" width="3" height="30" rx="1.2"/><rect x="5" y="4" width="12" height="2.6" rx="1.2"/>'
         '<rect x="1" y="10" width="20" height="3" rx="1.4"/>'
         '<rect x="4" y="19.4" width="14" height="2.6" rx="1.2" transform="rotate(-16 11 20.7)"/></g></svg>')
URLS = []


def badges(extra=""):
    return (f'<div class="badges{extra}">'
            f'<a class="b-ios" href="{IOS_URL}"><img src="{P}/assets/img/badge-app-store.svg" width="144" height="48" alt="Download on the App Store"></a>'
            f'<a class="b-play" href="{e(PLAY_URL)}"><img src="{P}/assets/img/badge-google-play.webp" width="161" height="48" alt="Get it on Google Play"></a>'
            f'</div>')


def app_card(text):
    return (f'<aside class="side"><div class="app"><div class="who">'
            f'<img src="{P}/assets/img/app-icon.webp" width="54" height="54" alt="">'
            f'<div><b>Orthodox Calendar</b><span>Free for iPhone and Android</span></div></div>'
            f'<p>{text}</p>{badges()}</div></aside>')


def crumbs_html(crumbs):
    parts = [f'<a href="{P}/">Home</a>']
    for label, url in crumbs[:-1]:
        parts.append(f'<a href="{url}">{e(label)}</a>')
    parts.append(e(crumbs[-1][0]))
    return '<p class="crumbs">' + "<span>/</span>".join(parts) + "</p>"


def crumbs_ld(crumbs, path):
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + P + "/"}]
    for i, (label, url) in enumerate(crumbs, 2):
        items.append({"@type": "ListItem", "position": i, "name": label,
                      "item": ORIGIN + (url if url else P + path)})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def page(path, title, desc, body, *, nav=None, ld=(), og_image=None, app_arg=None, og_type="website",
         index=True, in_sitemap=True, cta=True):
    url = ORIGIN + P + path
    og = og_image or f"{ORIGIN}{P}/assets/img/og.png"
    banner = f"app-id={APP_ID}" + (f", app-argument={ORIGIN}{P}{app_arg}" if app_arg else "")
    lds = "".join('<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False, separators=(",", ":"))
                  .replace("</", "<\\/") + "</script>" for x in ld)
    navs = [("today", "Today", f"{P}/today/"), ("calendar", "Calendar", f"{P}/calendar/"),
            ("names", "Name days", f"{P}/name-days/"), ("saints", "Saints", f"{P}/saints/"),
            ("guides", "Guides", f"{P}/guides/")]
    nav_html = "".join(f'<a href="{u}"{" aria-current=\"page\"" if k == nav else ""}>{t}</a>' for k, t, u in navs)
    closing = (f'<section class="cta"><div class="wrap"><img class="icon" src="{P}/assets/img/app-icon.webp" width="104" height="104" loading="lazy" alt="Orthodox Calendar app icon">'
               f'<div><h2>The calendar, on your phone each morning</h2><p>Today’s saints, whether it is a fast day, and the people in your contacts who have a name day. Free, with no ads.</p>{badges()}</div></div></section>'
               if cta else "")
    doc = f"""<!DOCTYPE html>
<html lang="en" data-p="{P}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="{'index, follow, max-image-preview:large' if index else 'noindex'}">
<meta name="apple-itunes-app" content="{banner}">
<meta name="theme-color" content="#131a5e">
<meta property="og:site_name" content="{SITE}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{P}/assets/img/app-icon-192.png">
<link rel="apple-touch-icon" href="{P}/assets/img/app-icon-192.png">
<link rel="preload" href="{P}/assets/fonts/alegreya-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{P}/assets/site.css?v={CSS_V}">
<script defer src="{P}/assets/site.js?v={JS_V}"></script>
<script defer src="{P}/assets/analytics.js?v={GA_V}"></script>
{lds}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
<a class="brand" href="{P}/">{CROSS}Orthodox Calendar</a>
<nav class="nav" aria-label="Main">{nav_html}<a class="get" href="{P}/get/">Get the app</a></nav>
</div></header>
<main id="main">
{body}
{closing}
</main>
<footer class="foot"><div class="wrap">
<div><b>Calendar</b><a href="{P}/today/">Saints and name days today</a><a href="{P}/calendar/">The year, day by day</a><a href="{P}/name-days/">Name days, A to Z</a><a href="{P}/saints/">Saints, A to Z</a></div>
<div><b>Guides</b><a href="{P}/guides/what-is-a-name-day/">What is a name day?</a><a href="{P}/guides/orthodox-easter-date/">When is Orthodox Easter?</a><a href="{P}/guides/orthodox-fasting-calendar/">The fasting calendar</a><a href="{P}/guides/">All guides</a></div>
<div><b>The app</b><a href="{IOS_URL}">iPhone, on the App Store</a><a href="{e(PLAY_URL)}">Android, on Google Play</a><a href="{P}/support.html">Support</a><a href="{P}/privacy-policy.html">Privacy policy</a></div>
<p class="legal">© {TODAY.year} 2pensmedia Inc. Dates are given on the New (Revised Julian) Calendar unless a page says otherwise. Follow your parish for liturgical practice.</p>
</div></footer>
<div class="getbar" data-getbar hidden><img src="{P}/assets/img/app-icon.webp" width="42" height="42" alt=""><div><b>Orthodox Calendar</b><span>Free, no ads</span></div><a href="{P}/get/">Get the app</a><button type="button" aria-label="Hide">×</button></div>
</body>
</html>
"""
    out = os.path.join(ROOT, path.lstrip("/"))
    if path.endswith("/"):
        out = os.path.join(out, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    if in_sitemap and index:
        URLS.append(url)


def inner(crumbs, h1, head_extra, main, side, right=""):
    return (f'<div class="head"><div class="wrap"><div>{crumbs_html(crumbs)}<h1>{h1}</h1>{head_extra}</div>{right}</div></div>'
            f'<div class="body"><div class="wrap"><div class="main">{main}</div>{side}</div></div>')


def saint_thumb(s):
    ic = ICONS.get(s["slug"])
    if ic:
        return f'<img src="{P}/assets/icons/t/{ic["img"]}.webp" width="120" height="160" loading="lazy" alt="Icon of {e(s["name"])}">'
    return f'<div class="ph">{CROSS}</div>'


def saint_li(s, with_date=False, para=True):
    names = all_names(s)
    nm = f'<p class="nm">Name days: {", ".join(name_link(n) for n in names)}</p>' if names else ""
    date = f'{fmt(s["m"], s["d"])}, ' if with_date else ""
    body = f"<p>{e(first_para(s['bio']))}</p>" if para else f"<p>{e(s['desc'])}</p>"
    return (f'<li class="{"gf" if s["type"] == "greatFeast" else ""}">{saint_thumb(s)}<div>'
            f'<h3><a href="{saint_url(s)}">{e(s["name"])}</a></h3>'
            f'<p class="sub">{date}{e(RANK[s["type"]])}, <span lang="el">{e(s["greek"])}</span></p>'
            f'{body}{nm}</div></li>')


def leaf(md):
    """Static leaf for one date; site.js redraws it for the visitor's own today."""
    m, d = md
    date = datetime.date(TODAY.year, m, d)
    saints = DAYS[md]
    lis = "".join(f'<li class="{"gf" if s["type"] == "greatFeast" else ""}"><a href="{saint_url(s)}">{e(s["name"])}</a>'
                  f'<span>{RANK[s["type"]]}</span></li>' for s in saints)
    names = []
    for s in saints:
        for n in all_names(s):
            if n not in names:
                names.append(n)
    nm = ""
    if names:
        nm = "<b>Name days </b>" + ", ".join(name_link(n) for n in names[:14])
        if len(names) > 14:
            nm += f" and {len(names) - 14} more"
    red = " red" if is_gf(md) or date.weekday() == 6 else ""
    return (f'<div class="leaf" data-leaf>'
            f'<div class="leaf-tear" aria-hidden="true"><span class="leaf-wd"></span><span class="leaf-num"></span><span class="leaf-my"></span></div>'
            f'<div class="leaf-head"><span class="leaf-wd">{date.strftime("%A")}</span><span class="leaf-num{red}">{d}</span>'
            f'<span class="leaf-my">{MONTHS[m - 1]} {date.year}</span></div>'
            f'<div class="leaf-cal" role="group" aria-label="Church calendar"><button type="button" data-cal="new" aria-pressed="true">New Calendar</button>'
            f'<button type="button" data-cal="old" aria-pressed="false">Old Calendar</button></div>'
            f'<p class="leaf-note" hidden></p>'
            f'<ul class="leaf-saints">{lis}</ul><p class="leaf-names">{nm}</p>'
            f'<a class="leaf-more" href="{day_url(m, d)}">Everything for {fmt(m, d)}</a></div>')


# ---------------------------------------------------------------- guides
def load_guides():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "_tools/guides/*.html"))):
        head, body = open(f, encoding="utf-8").read().split("\n---\n", 1)
        meta = dict(line.split(": ", 1) for line in head.splitlines())
        meta["body"] = body.strip().replace("{P}", P)
        meta["related"] = [x.strip() for x in meta["related"].split(",")]
        out[os.path.basename(f)[:-5]] = meta
    return out


GUIDES = load_guides()
GUIDE_ORDER = ["what-is-a-name-day", "greek-name-day-today", "chronia-polla-name-day-wishes",
               "old-calendar-vs-new-calendar", "orthodox-easter-date", "orthodox-fasting-calendar",
               "orthodox-feast-days"]


def guides_list(slugs):
    return '<ul class="guides">' + "".join(
        f'<li><a href="{P}/guides/{g}/">{GUIDES[g]["h1"]}</a><p>{e(GUIDES[g]["description"])}</p></li>' for g in slugs) + "</ul>"


def build_guides():
    for slug, g in GUIDES.items():
        path = f"/guides/{slug}/"
        crumbs = [("Guides", f"{P}/guides/"), (html.unescape(g["h1"]), None)]
        main = g["body"]
        if slug == "greek-name-day-today":
            main = main.replace("</p>", f'</p><p>See <a href="{P}/today/">today’s saints and name days</a>, or look up a name in the <a href="{P}/name-days/">name day index</a>.</p>', 1)
        main += (f'<h2>How the Orthodox Calendar app helps</h2><p>{g["assist"]}</p>{badges()}'
                 f'<h2>Related guides</h2>{guides_list(g["related"])}')
        ld = [crumbs_ld(crumbs, path),
              {"@context": "https://schema.org", "@type": "Article", "headline": html.unescape(g["h1"]),
               "description": g["description"], "datePublished": PUBLISHED, "dateModified": TODAY.isoformat(),
               "mainEntityOfPage": ORIGIN + P + path, "image": f"{ORIGIN}{P}/assets/img/og.png",
               "author": {"@type": "Organization", "name": "2pensmedia Inc."},
               "publisher": {"@type": "Organization", "name": SITE}}]
        page(path, g["title"], g["description"],
             inner(crumbs, g["h1"], "", main,
                   app_card("Today’s saints, fast days and your contacts’ name days, every morning on your phone.")),
             nav="guides", ld=ld, og_type="article")
    crumbs = [("Guides", None)]
    page("/guides/", "Orthodox calendar guides: name days, Pascha, fasting and feasts",
         "Plain guides to the Orthodox calendar: what a name day is, how the date of Pascha is set, the fasting seasons, the great feasts and the Old and New calendars.",
         inner(crumbs, "Guides to the Orthodox calendar",
               '<p class="meta">Short, careful answers to the questions people ask most about name days, feasts, fasts and the two calendars.</p>',
               guides_list(GUIDE_ORDER),
               app_card("Today’s saints, fast days and your contacts’ name days, every morning on your phone.")),
         nav="guides", ld=[crumbs_ld(crumbs, "/guides/")])


# ---------------------------------------------------------------- calendar
def build_days():
    for i, md in enumerate(ORDER):
        m, d = md
        saints = DAYS[md]
        path = f"/calendar/{day_slug(m, d)}/"
        label = fmt(m, d)
        names = []
        for s in saints:
            for n in all_names(s):
                if n not in names:
                    names.append(n)
        crumbs = [("Calendar", f"{P}/calendar/"), (MONTHS[m - 1], f"{P}/calendar/{MONTHS[m - 1].lower()}/"), (label, None)]
        head = (f'<p class="meta">The Orthodox Church commemorates {len(saints)} saints and feasts on {label}. '
                f'Churches on the Old (Julian) Calendar keep this day on <b>{old_note(m, d)}</b> of the civil calendar.</p>')
        main = ""
        if names:
            main += (f'<h2>Name days on {label}</h2><p class="names">{", ".join(name_link(n) for n in names)}</p>')
        else:
            main += (f'<h2>Name days on {label}</h2><p>None of the saints of this day carries a name in common use, '
                     f'so there are no widely kept name days on {label}.</p>')
        main += f'<h2>Saints and feasts of {label}</h2><ul class="saints">{"".join(saint_li(s) for s in saints)}</ul>'
        pm, pd = ORDER[i - 1]
        nm, nd = ORDER[(i + 1) % len(ORDER)]
        main += (f'<nav class="pn" aria-label="Neighbouring days"><a href="{day_url(pm, pd)}" rel="prev">{fmt(pm, pd)}</a>'
                 f'<a href="{day_url(nm, nd)}" rel="next">{fmt(nm, nd)}</a></nav>')
        title = f"{label}: Orthodox saints and name days"
        desc = trim(f"Orthodox saints and feasts on {label}: {join_names([s['name'] for s in saints], 4)}."
                    + (f" Name days: {join_names(names, 8)}." if names else ""), 300)
        mini = f'<div class="mini{" red" if is_gf(md) else ""}" aria-hidden="true"><b>{d}</b><span>{MONTHS[m - 1]}</span></div>'
        page(path, title, trim(desc, 160),
             inner(crumbs, f"Orthodox saints and name days on {label}", head, main,
                   app_card(f"See the saints of each day on your phone, with a morning reminder when someone in your contacts has a name day."),
                   right=mini),
             nav="calendar", ld=[crumbs_ld(crumbs, path)], app_arg=f"/saint/?d={m}-{d}")


def build_months():
    for m in range(1, 13):
        name = MONTHS[m - 1]
        path = f"/calendar/{name.lower()}/"
        rows = ""
        for d in range(1, MDAYS[m - 1] + 1):
            saints = DAYS[(m, d)]
            sn = ", ".join(f'<a class="{"gf" if s["type"] == "greatFeast" else ""}" href="{saint_url(s)}">{e(s["name"])}</a>' for s in saints[:4])
            if len(saints) > 4:
                sn += f" and {len(saints) - 4} more"
            names = []
            for s in saints:
                for n in all_names(s):
                    if n not in names:
                        names.append(n)
            nn = ", ".join(name_link(n) for n in names[:10])
            if len(names) > 10:
                nn += f" and {len(names) - 10} more"
            rows += f'<tr><td class="d"><a href="{day_url(m, d)}">{name} {d}</a></td><td>{sn}</td><td class="n">{nn}</td></tr>'
        pm, nm = MONTHS[(m - 2) % 12], MONTHS[m % 12]
        main = (f'<div class="tbl"><table class="mt"><tr><th>Date</th><th>Saints and feasts</th><th>Name days</th></tr>{rows}</table></div>'
                f'<nav class="pn" aria-label="Neighbouring months"><a href="{P}/calendar/{pm.lower()}/" rel="prev">{pm}</a>'
                f'<a href="{P}/calendar/{nm.lower()}/" rel="next">{nm}</a></nav>')
        crumbs = [("Calendar", f"{P}/calendar/"), (name, None)]
        om, od = old_civil(m, 1)
        head = (f'<p class="meta">Every day of {name} with its saints, feasts and name days, on the New Calendar. '
                f'Old Calendar churches keep each of these days 13 days later, so {name} 1 falls on {fmt(om, od)}.</p>')
        body = (f'<div class="head"><div class="wrap"><div>{crumbs_html(crumbs)}<h1>Orthodox calendar for {name}</h1>{head}</div></div></div>'
                f'<div class="body"><div class="wrap" style="display:block">{main}</div></div>')
        page(path, f"Orthodox calendar for {name}: saints and name days by day",
             f"The Orthodox calendar for {name}: the saints, feasts and name days of every day of the month, with Old Calendar dates.",
             body, nav="calendar", ld=[crumbs_ld(crumbs, path)])


def year_grid():
    out = '<div class="year">'
    for m in range(1, 13):
        cells = "".join(f'<li><a{" class=\"gf\"" if is_gf((m, d)) else ""} href="{day_url(m, d)}">{d}</a></li>'
                        for d in range(1, MDAYS[m - 1] + 1))
        out += f'<section><h2><a href="{P}/calendar/{MONTHS[m - 1].lower()}/">{MONTHS[m - 1]}</a></h2><ol>{cells}</ol></section>'
    return out + "</div>"


def build_calendar_index():
    crumbs = [("Calendar", None)]
    head = ('<p class="meta">Pick any day of the year to see the saints the Orthodox Church commemorates and the name days kept on it.</p>')
    body = (f'<div class="head"><div class="wrap"><div>{crumbs_html(crumbs)}<h1>The Orthodox calendar, day by day</h1>{head}</div></div></div>'
            f'<div class="body"><div class="wrap" style="display:block"><p class="key">Days in <b>red</b> are great feasts. '
            f'Dates follow the New (Revised Julian) Calendar; Old Calendar churches keep each day 13 days later.</p>{year_grid()}</div></div>')
    page("/calendar/", "Orthodox calendar: saints, feasts and name days for every day",
         "The Orthodox Church calendar for the whole year. Choose any date to see its saints, feasts and name days, on the New or Old Calendar.",
         body, nav="calendar", ld=[crumbs_ld(crumbs, "/calendar/")])


# ---------------------------------------------------------------- saints
def build_saints():
    for slug, entries in SAINTS.items():
        s = entries[0]
        path = f"/saints/{slug}/"
        ic = ICONS.get(slug)
        dates = join_names([fmt(x["m"], x["d"]) for x in entries]).replace(", ", " and ")
        crumbs = [("Saints", f"{P}/saints/"), (s["name"], None)]
        gf = s["type"] == "greatFeast"
        head = (f'<p class="greek" lang="el">{e(s["greek"])}</p>'
                f'<p class="rank{" gf" if gf else ""}">{RANK[s["type"]]}</p>'
                f'<p class="meta">Feast day <b>{dates}</b></p>')
        right = (f'<img class="icon" src="{P}/assets/icons/{ic["img"]}.webp" width="360" height="480" alt="Icon of {e(s["name"])}">'
                 if ic else "")
        main = f'<p class="lead">{e(s["desc"])}</p>'
        if len(entries) == 1:
            main += paras(s["bio"])
        else:
            seen = set()
            for x in entries:
                if x["bio"] in seen:
                    continue
                seen.add(x["bio"])
                main += f'<h2>{fmt(x["m"], x["d"])}</h2>{paras(x["bio"])}'
        main += "<h2>Feast day</h2>"
        for x in entries:
            main += (f'<p>On the New Calendar, {e(s["name"])} is commemorated on <a href="{day_url(x["m"], x["d"])}">{fmt(x["m"], x["d"])}</a>. '
                     f'Churches on the Old (Julian) Calendar keep the feast on {old_note(x["m"], x["d"])} of the civil calendar.</p>')
        names = []
        for x in entries:
            for n in all_names(x):
                if n not in names:
                    names.append(n)
        if names:
            main += (f'<h2>Who celebrates a name day</h2><p>People with these names keep their name day on this feast:</p>'
                     f'<p class="names">{", ".join(name_link(n) for n in names)}</p>')
        others = [o for o in DAYS[(s["m"], s["d"])] if o["slug"] != slug]
        if others:
            main += (f'<h2>Also commemorated on {fmt(s["m"], s["d"])}</h2><ul class="saints">'
                     f'{"".join(saint_li(o, para=False) for o in others)}</ul>')
        if ic and ic.get("src"):
            main += f'<p class="note">Icon: public domain image from <a href="{e(ic["src"])}" rel="noopener">Wikimedia Commons</a>.</p>'
        title = f"{s['name']}: life and feast day, {fmt(s['m'], s['d'])}"
        desc = trim(f"{s['desc']} Feast day {dates}. " + first_para(s["bio"]), 160)
        ld = [crumbs_ld(crumbs, path),
              {"@context": "https://schema.org", "@type": "Article", "headline": s["name"], "description": s["desc"],
               "datePublished": PUBLISHED, "dateModified": TODAY.isoformat(), "mainEntityOfPage": ORIGIN + P + path,
               "image": (f"{ORIGIN}{P}/assets/icons/{ic['img']}.webp" if ic else f"{ORIGIN}{P}/assets/img/og.png"),
               "author": {"@type": "Organization", "name": "2pensmedia Inc."},
               "publisher": {"@type": "Organization", "name": SITE}}]
        page(path, title, desc,
             inner(crumbs, e(s["name"]), head, main,
                   app_card("Read the life of a saint like this every morning. The app shows each day’s saints and tells you when a friend has a name day."),
                   right=right),
             nav="saints", ld=ld, og_type="article",
             app_arg=f"/saint/?d={s['m']}-{s['d']}&s={slug}")

    groups = {}
    for slug, entries in SAINTS.items():
        s = entries[0]
        key = fold(re.sub(r"^(Sts?\.|Saints?|Holy|The)\s+", "", s["name"]))
        letter = key[0].upper() if key[0].isalpha() else "#"
        groups.setdefault(letter, []).append((key, s))
    letters = sorted(groups)
    az = '<nav class="az" aria-label="Jump to letter">' + "".join(f'<a href="#l-{l if l != "#" else "num"}">{l}</a>' for l in letters) + "</nav>"
    secs = ""
    for l in letters:
        lis = "".join(f'<li><a href="{saint_url(s)}">{e(s["name"])}</a> <small>{MONTHS[s["m"] - 1][:3]} {s["d"]}</small></li>'
                      for _, s in sorted(groups[l], key=lambda t: t[0]))
        secs += f'<section id="l-{l if l != "#" else "num"}"><h2>{l}</h2><ul>{lis}</ul></section>'
    crumbs = [("Saints", None)]
    head = f'<p class="meta">{len(SAINTS):,} saints and feasts of the Orthodox Church, each with a short life and its feast day.</p>'
    body = (f'<div class="head"><div class="wrap"><div>{crumbs_html(crumbs)}<h1>Orthodox saints, A to Z</h1>{head}</div></div></div>'
            f'<div class="body"><div class="wrap" style="display:block"><div class="filter"><label class="vh" for="flt">Filter saints</label>'
            f'<input id="flt" type="search" data-filter placeholder="Filter, for example Nicholas or martyr" autocomplete="off"></div>'
            f'{az}<div class="idx wide">{secs}</div></div></div>')
    page("/saints/", "Orthodox saints A to Z: lives and feast days",
         f"An index of {len(SAINTS):,} Orthodox saints and feasts. Read a short life of each saint and find the feast day on the New and Old calendars.",
         body, nav="saints", ld=[crumbs_ld(crumbs, "/saints/")])


# ---------------------------------------------------------------- name days
def build_names():
    for nslug, rec in NAMES.items():
        name, feasts = rec["name"], rec["feasts"]
        path = f"/name-days/{nslug}/"
        prim = primary_feast(rec)
        lead = prim or feasts[0]
        crumbs = [("Name days", f"{P}/name-days/"), (name, None)]
        ordered = ([prim] + [f for f in feasts if f is not prim]) if prim else feasts
        if len(feasts) == 1:
            s = feasts[0]
            answer = (f'{e(poss(name))} name day is <strong>{fmt(s["m"], s["d"])}</strong>, the feast of {the(s)}'
                      f'<a href="{saint_url(s)}">{e(s["name"])}</a>.')
            title = f"{name} name day: {fmt(s['m'], s['d'])} in the Orthodox calendar"
            desc = (f"{poss(name)} name day is {fmt(s['m'], s['d'])}, the feast of {the(s)}{s['name']}. "
                    f"Old Calendar date: {fmt(*old_civil(s['m'], s['d']))}. See who else celebrates and what to say.")
        else:
            if prim:
                answer = (f'Most people named {e(name)} keep their name day on <strong>{fmt(prim["m"], prim["d"])}</strong>, '
                          f'the feast of {the(prim)}<a href="{saint_url(prim)}">{e(prim["name"])}</a>. '
                          f'The Orthodox calendar has {len(feasts) - 1} other {"feast" if len(feasts) == 2 else "feasts"} for the name.')
                title = f"{name} name day: {fmt(prim['m'], prim['d'])} and {len(feasts) - 1} more {'date' if len(feasts) == 2 else 'dates'}"
                desc = (f"{poss(name)} name day is most often kept on {fmt(prim['m'], prim['d'])}, the feast of {the(prim)}{prim['name']}. "
                        f"See {'both' if len(feasts) == 2 else 'all ' + str(len(feasts))} Orthodox feasts for the name, with Old Calendar dates.")
            else:
                answer = (f'{e(name)} can be celebrated on <strong>{len(feasts)} feasts</strong> in the Orthodox calendar. '
                          f'People keep the feast of the saint they were named for, or the one their family has always kept.')
                title = f"{name} name day: {len(feasts)} dates in the Orthodox calendar"
                desc = (f"{name} has {len(feasts)} name days in the Orthodox calendar: "
                        f"{join_names([fmt(s['m'], s['d']) for s in feasts], 5)}. See the saint behind each date.")
        main = f'<p class="answer">{answer}</p>'
        if len(feasts) > 1:
            rows = "".join(
                f'<tr><td class="d"><a href="{day_url(s["m"], s["d"])}">{fmt(s["m"], s["d"])}</a></td>'
                f'<td><a class="{"gf" if s["type"] == "greatFeast" else ""}" href="{saint_url(s)}">{e(s["name"])}</a></td>'
                f'<td>{fmt(*old_civil(s["m"], s["d"]))}</td></tr>' for s in feasts)
            main += (f'<h2>Every feast on which {e(name)} is celebrated</h2><div class="tbl"><table>'
                     f'<tr><th>New Calendar</th><th>Feast</th><th>Old Calendar (civil date)</th></tr>{rows}</table></div>')
        else:
            s = feasts[0]
            main += (f'<p>Churches that follow the Old (Julian) Calendar keep the same feast on '
                     f'{old_note(s["m"], s["d"])} of the civil calendar. See everything commemorated on '
                     f'<a href="{day_url(s["m"], s["d"])}">{fmt(s["m"], s["d"])}</a>.</p>')
        if any((s["m"], s["d"]) == (4, 23) and "George" in s["name"] for s in feasts):
            main += ('<p class="note">Saint George’s feast moves in some years. When April 23 falls before Pascha, '
                     f'it is kept on Bright Monday, the day after Pascha. See <a href="{P}/guides/orthodox-easter-date/">when Pascha falls</a>.</p>')
        main += (f'<h2>{"The saint" if len(feasts) == 1 else "The saints"} behind the name</h2><ul class="saints">'
                 f'{"".join(saint_li(s, with_date=True) for s in ordered[:3])}</ul>')
        if len(ordered) > 3:
            main += f'<p>The other feasts are listed in the table above, each with a link to the saint’s life.</p>'
        sibs = []
        for s in (ordered if len(feasts) == 1 or not prim else [prim]):
            for n in all_names(s):
                if slugify(n) != nslug and n not in sibs:
                    sibs.append(n)
        if sibs:
            on = fmt(lead["m"], lead["d"])
            main += (f'<h2>Also celebrating {"on " + on if len(feasts) == 1 or prim else "with " + e(name)}</h2>'
                     f'<p>These names share the feast, many of them other forms of the same name:</p>'
                     f'<p class="names">{", ".join(name_link(n) for n in sibs[:60])}</p>')
        main += (f'<h2>What to say on a name day</h2><p>The Greek wish is <strong lang="el">Χρόνια Πολλά</strong> '
                 f'(Chronia Polla), “many years.” A call or a short message on the day is what people remember. '
                 f'See <a href="{P}/guides/chronia-polla-name-day-wishes/">name day wishes you can send</a> and '
                 f'<a href="{P}/guides/what-is-a-name-day/">what a name day is</a>.</p>')
        head = ""
        page(path, title, trim(desc, 160),
             inner(crumbs, f"When is {e(poss(name))} name day?", head, main,
                   app_card(f"Know someone named {e(name)}? The app checks your contacts each morning and tells you who has a name day, so you can wish them in one tap.")),
             nav="names", ld=[crumbs_ld(crumbs, path)],
             app_arg=f"/saint/?d={lead['m']}-{lead['d']}&s={lead['slug']}")

    groups = {}
    for nslug, rec in NAMES.items():
        groups.setdefault(nslug[0].upper(), []).append((nslug, rec))
    letters = sorted(groups)
    az = '<nav class="az" aria-label="Jump to letter">' + "".join(f'<a href="#l-{l}">{l}</a>' for l in letters) + "</nav>"
    secs = ""
    for l in letters:
        lis = ""
        for nslug, rec in sorted(groups[l]):
            f0 = primary_feast(rec) or rec["feasts"][0]
            extra = f" +{len(rec['feasts']) - 1}" if len(rec["feasts"]) > 1 else ""
            lis += (f'<li><a href="{P}/name-days/{nslug}/">{e(rec["name"])}</a> '
                    f'<small>{MONTHS[f0["m"] - 1][:3]} {f0["d"]}{extra}</small></li>')
        secs += f'<section id="l-{l}"><h2>{l}</h2><ul>{lis}</ul></section>'
    crumbs = [("Name days", None)]
    head = (f'<p class="meta">{len(NAMES):,} names and the feast on which each is celebrated in the Orthodox Church. '
            f'Dates follow the New Calendar; each name page gives the Old Calendar date too.</p>')
    body = (f'<div class="head"><div class="wrap"><div>{crumbs_html(crumbs)}<h1>Orthodox name days, A to Z</h1>{head}</div></div></div>'
            f'<div class="body"><div class="wrap" style="display:block"><div class="filter"><label class="vh" for="flt">Filter names</label>'
            f'<input id="flt" type="search" data-filter placeholder="Type a name, like Eleni or George" autocomplete="off"></div>'
            f'{az}<div class="idx">{secs}</div></div></div>')
    page("/name-days/", "Orthodox name days A to Z: find the date for any name",
         f"Look up the Orthodox name day for {len(NAMES):,} names, Greek and English forms alike. See the date, the saint and the Old Calendar date.",
         body, nav="names", ld=[crumbs_ld(crumbs, "/name-days/")])


# ---------------------------------------------------------------- home, today, 404
FAQ = [
    ("What is an Orthodox name day?",
     "A name day is the feast day of the saint whose name you carry. In Orthodox cultures it is celebrated much like a birthday, and often more, with visits, calls and the wish Χρόνια Πολλά.",
     "/guides/what-is-a-name-day/"),
    ("Whose name day is it today?",
     "Every day the Church commemorates particular saints, and everyone who shares their name celebrates. The calendar leaf at the top of this page shows today’s saints and names, and the app matches them to your contacts.",
     "/today/"),
    ("Is the app free?",
     "Yes. Orthodox Calendar is free for iPhone and Android, has no ads and needs no account. There is an optional tip jar for people who want to support it.", None),
    ("Are my contacts private?",
     "Yes. Your contacts are read on your phone only. They are never uploaded, stored or shared, and name days you assign by hand stay on your device.", "/privacy-policy.html"),
    ("What is the difference between the Old and New Orthodox calendars?",
     "Old Calendar churches keep the Julian calendar, which currently runs 13 days behind civil dates, so Christmas falls on January 7. New Calendar churches keep the Revised Julian calendar, which matches civil dates. The app switches between them in one tap.",
     "/guides/old-calendar-vs-new-calendar/"),
    ("When is Orthodox Easter?",
     "Pascha is the first Sunday after the first full moon on or after the spring equinox, reckoned on the Julian calendar. It falls on April 12 in 2026, May 2 in 2027 and April 16 in 2028.",
     "/guides/orthodox-easter-date/"),
    ("Does the app show fast days?",
     "Yes. It shows whether today is a fast day and what is permitted: strict fast, wine and oil, fish, or fast free. It covers Great Lent, the Apostles’, Dormition and Nativity fasts, and Wednesdays and Fridays.",
     "/guides/orthodox-fasting-calendar/"),
    ("What does Χρόνια Πολλά mean?",
     "It means “many years,” the traditional wish for name days, birthdays and feasts. The app sends a ready-made Χρόνια Πολλά card and message in one tap.",
     "/guides/chronia-polla-name-day-wishes/"),
]
SHOTS = [
    ("01-name-day", "Checks your contacts for name days",
     "Today’s saints are matched to the names in your contacts, on your phone. Nothing is uploaded."),
    ("02-orthodox-saints", "Tells the life of each saint",
     "A short life, the Greek name and the rank of the feast, with icons for hundreds of saints."),
    ("03-orthodox-calendar", "Shows the whole month",
     "Feast days and fast days are marked, on the Old Calendar or the New."),
    ("04-fast-day", "Says whether today is a fast",
     "Strict fast, wine and oil, fish or fast free, following the Greek Orthodox Archdiocese guidelines."),
    ("05-chronia-polla", "Sends Χρόνια Πολλά for you",
     "A ready-made greeting card and message, in Greek, English or both."),
]


def name_finder():
    return ('<form class="namefind" data-namefind role="search"><label for="nf">Name</label>'
            '<input id="nf" type="search" autocomplete="off" placeholder="Type a name, like Eleni or George">'
            '<ul class="nf-results" hidden></ul></form>')


def build_home():
    md = (TODAY.month, TODAY.day)
    shots = "".join(
        f'<figure><img src="{P}/assets/img/shot-{f}.webp" width="520" height="1127" loading="lazy" alt="Orthodox Calendar app: {e(t.lower())}">'
        f'<figcaption><b>{t}</b>{e(c)}</figcaption></figure>' for f, t, c in SHOTS)
    pop = ""
    for n in POPULAR:
        rec = NAMES.get(slugify(n))
        if not rec:
            continue
        f0 = primary_feast(rec) or rec["feasts"][0]
        pop += f'<li><a href="{P}/name-days/{slugify(n)}/">{e(rec["name"])}</a><span>{fmt(f0["m"], f0["d"])}</span></li>'
    months = "".join(f'<a href="{P}/calendar/{m.lower()}/">{m}</a>' for m in MONTHS)
    faq = ""
    for q, a, link in FAQ:
        more = f' <a href="{P}{link}">Read more</a>' if link else ""
        faq += f"<details><summary>{e(q)}</summary><p>{e(a)}{more}</p></details>"
    body = f"""<section class="hero"><div class="wrap">
<div><h1>The Orthodox calendar of saints and name days</h1>
<p class="sub">See who the Church commemorates today, whether it is a fast day, and which of your family and friends are celebrating their name day.</p>
{badges()}
<p class="terms">Free for iPhone and Android. No ads, no account.</p></div>
{leaf(md)}
</div></section>
<section class="sec"><div class="wrap"><h2>When is your name day?</h2>
<p class="intro">Look up any of {len(NAMES):,} names, in their Greek and English forms, and see the feast behind each one.</p>
{name_finder()}
<ul class="pairs">{pop}</ul>
<p style="margin-top:1.2rem"><a href="{P}/name-days/">All name days, A to Z</a></p></div></section>
<section class="sec alt"><div class="wrap"><h2>What the app does each morning</h2>
<p class="intro">One look tells you the saints of the day, the fast, and who to call.</p>
<div class="shots">{shots}</div></div></section>
<section class="sec"><div class="wrap"><h2>Browse the year</h2>
<p class="intro">Every day has its saints. Choose a month, or go straight to <a href="{P}/today/">today</a>.</p>
<div class="months">{months}</div></div></section>
<section class="sec alt"><div class="wrap"><h2>Guides to the calendar</h2>{guides_list(GUIDE_ORDER[:6])}</div></section>
<section class="sec"><div class="wrap"><h2>Questions people ask</h2><div class="faq" style="margin-top:1.2rem">{faq}</div></div></section>
<section class="cta"><div class="wrap"><img class="icon" src="{P}/assets/img/app-icon.webp" width="104" height="104" alt="Orthodox Calendar app icon">
<div><h2>Never miss a name day again</h2><p>Open the app each morning for the saints of the day, the fast, and the people in your contacts who are celebrating.</p>{badges()}</div></div></section>"""
    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": ORIGIN + P + "/"},
        {"@context": "https://schema.org", "@type": "MobileApplication", "name": "Orthodox Calendar: Name Days",
         "operatingSystem": "iOS, Android", "applicationCategory": "LifestyleApplication",
         "description": "Daily Orthodox saints, feast days, fast days and name-day reminders on the Old and New calendars.",
         "image": f"{ORIGIN}{P}/assets/img/app-icon-192.png", "url": ORIGIN + P + "/",
         "installUrl": IOS_URL, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "author": {"@type": "Organization", "name": "2pensmedia Inc."}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, _ in FAQ]},
    ]
    page("/", "Orthodox Calendar: saints, feast days and name days for every day",
         "Today’s Orthodox saints, feast days, fast days and name days, on the Old and New calendars. Look up any name day, or get the free app for iPhone and Android.",
         body, ld=ld, cta=False)


def build_today():
    md = (TODAY.month, TODAY.day)
    crumbs = [("Today", None)]
    main = (f'{leaf(md)}<h2 style="margin-top:2.6rem">How this page works</h2>'
            f'<p>The leaf above shows the saints and name days for today’s date where you are. Switch to the Old Calendar to see '
            f'what churches on the Julian calendar keep today, which is the feast of the date 13 days earlier.</p>'
            f'<p>Tap a saint to read a short life, or a name to see every feast on which it is celebrated. '
            f'For any other date, open the <a href="{P}/calendar/">calendar for the whole year</a>.</p>'
            f'<h2>Get this every morning</h2><p>The Orthodox Calendar app shows the same leaf each day, adds whether it is a fast day, '
            f'and checks your contacts so you know who to wish Χρόνια Πολλά.</p>{badges()}')
    page("/today/", "Orthodox saints and name days today",
         "Today’s saints and feasts in the Orthodox Church and whose name day it is, on the New Calendar or the Old. Updated every day.",
         inner(crumbs, "Orthodox saints and name days today",
               '<p class="meta">The saints the Church commemorates today, and the names that celebrate.</p>', main,
               app_card("Get today’s saints, the fast and your contacts’ name days on your phone each morning.")),
         nav="today", ld=[crumbs_ld(crumbs, "/today/")])


def build_404():
    body = (f'<div class="head"><div class="wrap"><div><h1>That page is not in the calendar</h1>'
            f'<p class="meta">The address may have changed. Try one of these instead.</p></div></div></div>'
            f'<div class="body"><div class="wrap" style="display:block"><ul class="guides">'
            f'<li><a href="{P}/today/">Saints and name days today</a></li><li><a href="{P}/name-days/">Name days, A to Z</a></li>'
            f'<li><a href="{P}/calendar/">The calendar, day by day</a></li><li><a href="{P}/saints/">Saints, A to Z</a></li></ul></div></div>')
    page("/404.html", "Page not found", "This page does not exist.", body, index=False, in_sitemap=False)


# ---------------------------------------------------------------- data files + sitemap
def build_data():
    os.makedirs(os.path.join(ROOT, "assets/days"), exist_ok=True)
    for m in range(1, 13):
        data = {str(d): [{"n": s["name"], "s": s["slug"], "t": s["type"], "m": all_names(s)} for s in DAYS[(m, d)]]
                for d in range(1, MDAYS[m - 1] + 1)}
        json.dump(data, open(os.path.join(ROOT, f"assets/days/{m}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
    names = sorted((rec["name"] for rec in NAMES.values()), key=fold)
    json.dump(names, open(os.path.join(ROOT, "assets/names.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))


def build_sitemap():
    lastmod = TODAY.isoformat()
    body = "".join(f"<url><loc>{e(u)}</loc><lastmod>{lastmod}</lastmod></url>\n" for u in URLS)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")
    open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8").write(
        f"User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}{P}/sitemap.xml\n")


def main():
    for d in ("calendar", "name-days", "saints", "guides", "today", "assets/days"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)

    build_data()
    build_home()
    build_today()
    build_calendar_index()
    build_months()
    build_days()
    build_names()
    build_saints()
    build_guides()
    build_404()
    build_sitemap()
    print(f"{len(URLS)} pages: {len(ORDER)} days, {len(NAMES)} names, {len(SAINTS)} saints, {len(GUIDES)} guides")


if __name__ == "__main__":
    main()
