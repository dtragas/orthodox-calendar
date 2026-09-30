# Orthodox Calendar website generator

Everything public on the site except `get/`, `saint/`, `privacy-policy.html` and `support.html`
is written by `build.py`. This folder starts with an underscore so GitHub Pages does not publish it.

## Rebuild

    python3 _tools/build.py

Run it after every change to `saint/saints/*.json` (new saints, new names), to a guide in
`_tools/guides/`, or to the page templates in `build.py`. It deletes and rewrites
`calendar/`, `name-days/`, `saints/`, `guides/`, `today/`, `assets/days/`, plus `index.html`,
`404.html`, `sitemap.xml` and `assets/names.json`. Then commit and push to publish.

## Saint icons

    python3 _tools/prep_icons.py

Converts the app's public-domain saint icons (iOS asset catalog) to WebP and writes
`_tools/icons.json`. Run it when icons are added to the app, then run `build.py`.

## Domain

The site lives at https://orthodoxcalendar.net (`ORIGIN` and `PREFIX` at the top of `build.py`,
and the `CNAME` file). The old `dtragas.github.io/orthodox-calendar/` addresses redirect there.
`.well-known/` holds the files that let shared links open the iOS and Android apps.

## Hand-written files

`assets/site.css`, `assets/site.js`, `_tools/guides/*.html` (guide text), `_tools/og.html`
(source of `assets/img/og.png`, the link-preview image).

## Adding name-day names (both apps + this site)

Edit the table in `_tools/names_table.py` (key `"M-D-Saint name"`, masculine and feminine lists), then:

    python3 _tools/apply_names.py          # dry run, shows what would change
    python3 _tools/apply_names.py --write  # edits iOS Swift, Android Kotlin and saint/saints/*.json
    python3 _tools/build.py

It refuses to write if the three copies of a saint's name lists are out of sync.
