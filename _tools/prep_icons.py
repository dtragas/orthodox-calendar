#!/usr/bin/env python3
"""Convert the app's public-domain saint icons to WebP and map them to saints.

Reads the iOS asset catalog + its CREDITS.md, writes assets/icons/*.webp
(360x480), assets/icons/t/*.webp (120x160) and _tools/icons.json.
Re-run after adding icons to the app, then run build.py.
"""
import glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.expanduser("~/OrthodoxCalendar/OrthodoxCalendar/Assets.xcassets/SaintIcons")

saints = {}
for f in glob.glob(os.path.join(ROOT, "saint/saints/*.json")):
    for key, lst in json.load(open(f)).items():
        for s in lst:
            saints[f"{key}-{s['name']}"] = s["slug"]

# asset -> Wikimedia Commons source page, from the credits table
commons = {}
for line in open(os.path.join(SRC, "CREDITS.md"), encoding="utf-8"):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) >= 5 and re.match(r"^[a-z0-9_]+$", cells[0]) and cells[0] != "asset":
        commons[cells[0]] = cells[2]

# saint -> asset, straight from the Swift data (the credits table's dates go stale)
DATA = os.path.expanduser("~/OrthodoxCalendar/OrthodoxCalendar/Data")
out, missing = {}, []
for f in glob.glob(os.path.join(DATA, "**/*.swift"), recursive=True):
    src = open(f, encoding="utf-8").read()
    for block in re.split(r"(?=\bSaint\(name: \")", src)[1:]:
        m = re.match(r'Saint\(name: "((?:[^"\\]|\\.)*)".*?month: (\d+), day: (\d+)', block, re.S)
        im = re.search(r'imageName: "([a-z0-9_]+)"', block)
        if not m or not im:
            continue
        name = m.group(1).replace('\\"', '"')
        key = f"{int(m.group(2))}-{int(m.group(3))}-{name}"
        asset = im.group(1)
        if key not in saints:
            missing.append(("nosaint", asset, key)); continue
        imgs = glob.glob(os.path.join(SRC, asset + ".imageset", "*.jpg")) + glob.glob(os.path.join(SRC, asset + ".imageset", "*.png"))
        if not imgs:
            missing.append(("noimage", asset)); continue
        fname = asset.replace("_", "-")
        big = os.path.join(ROOT, "assets/icons", fname + ".webp")
        small = os.path.join(ROOT, "assets/icons/t", fname + ".webp")
        if not os.path.exists(big) or "--force" in sys.argv:
            subprocess.run(["magick", imgs[0], "-resize", "360x480^", "-gravity", "center", "-extent", "360x480", "-strip", "/tmp/_oc_icon.png"], check=True)
            subprocess.run(["cwebp", "-quiet", "-q", "72", "/tmp/_oc_icon.png", "-o", big], check=True)
            subprocess.run(["magick", imgs[0], "-resize", "120x160^", "-gravity", "center", "-extent", "120x160", "-strip", "/tmp/_oc_icon.png"], check=True)
            subprocess.run(["cwebp", "-quiet", "-q", "70", "/tmp/_oc_icon.png", "-o", small], check=True)
        out[saints[key]] = {"img": fname, "src": commons.get(asset, "")}

json.dump(out, open(os.path.join(ROOT, "_tools/icons.json"), "w"), ensure_ascii=False, indent=0, sort_keys=True)
print(len(out), "saints with icons;", len(missing), "unmatched")
for m in missing[:40]:
    print("  ", m)
