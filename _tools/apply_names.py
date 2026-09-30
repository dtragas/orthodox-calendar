#!/usr/bin/env python3
"""Add missing name-day names to the iOS data, the Android data and the web JSON in one pass.
Dry run by default; pass --write to save."""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from names_table import ADD, REMOVE

WRITE = "--write" in sys.argv
H = os.path.expanduser("~")
IOS = glob.glob(H + "/OrthodoxCalendar/OrthodoxCalendar/Data/Months/*.swift")
AND = glob.glob(H + "/OrthodoxCalendar-Android/app/src/main/java/com/twopensmedia/orthodoxcalendar/data/months/*.kt")
WEB = H + "/orthodox-calendar/saint/saints"


def dedupe(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


def plan(key, alt, fem):
    """New (alternateNames, feminineNames) for one saint from its current lists."""
    addm, addf = ADD[key]
    drop = REMOVE.get(key, [])
    alt = [n for n in dedupe(alt) if n not in drop]
    fem = [n for n in dedupe(fem) if n not in drop]
    for n in addm + addf:
        if n not in alt:
            alt.append(n)
    for n in addf:
        if n not in fem:
            fem.append(n)
    assert not (set(addm) & set(fem)), (key, set(addm) & set(fem))
    return alt, fem


def parse_list(src):
    return re.findall(r'"((?:[^"\\]|\\.)*)"', src or "")


def lit(xs):
    return ", ".join('"%s"' % x for x in xs)


# ---------------- web JSON (the reference: masc = alt - fem)
web_before, web_after = {}, {}
for m in range(1, 13):
    p = f"{WEB}/{m}.json"
    d = json.load(open(p, encoding="utf-8"))
    changed = False
    for daykey, lst in d.items():
        for s in lst:
            key = f"{daykey}-{s['name']}"
            if key not in ADD:
                continue
            alt0 = s["masc"] + s["fem"]
            web_before[key] = (set(alt0), set(s["fem"]))
            alt, fem = plan(key, alt0, s["fem"])
            s["masc"] = [n for n in alt if n not in fem]
            s["fem"] = fem
            web_after[key] = (alt, fem)
            changed = True
    if changed and WRITE:
        open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
assert set(web_after) == set(ADD), set(ADD) - set(web_after)

# ---------------- iOS Swift
done = set()
for p in IOS:
    src = open(p, encoding="utf-8").read()
    out, pos = [], 0
    for mt in re.finditer(r'Saint\(name: "((?:[^"\\]|\\.)*)", greekName: [^\n]*?month: (\d+), day: (\d+)', src):
        key = f"{mt.group(2)}-{mt.group(3)}-{mt.group(1)}"
        if key not in ADD:
            continue
        lm = re.compile(r'alternateNames: \[(.*?)\](,\s*feminineNames: \[(.*?)\])?', re.S).search(src, mt.end())
        nxt = src.find("Saint(name:", mt.end())
        assert lm and (nxt < 0 or lm.start() < nxt), key
        alt0, fem0 = parse_list(lm.group(1)), parse_list(lm.group(3))
        assert (set(alt0), set(fem0)) == web_before[key], ("iOS differs from web", key, alt0, fem0)
        alt, fem = plan(key, alt0, fem0)
        new = f"alternateNames: [{lit(alt)}]" + (f", feminineNames: [{lit(fem)}]" if fem else "")
        out.append(src[pos:lm.start()] + new)
        pos = lm.end()
        done.add(key)
    if out:
        out.append(src[pos:])
        if WRITE:
            open(p, "w", encoding="utf-8").write("".join(out))
assert done == set(ADD), ("iOS missing", set(ADD) - done)

# ---------------- Android Kotlin
done = set()
for p in AND:
    lines = open(p, encoding="utf-8").read().split("\n")
    touched = False
    for i, line in enumerate(lines):
        mt = re.match(r'\s*Saint\("((?:[^"\\]|\\.)*)", (?:"(?:[^"\\]|\\.)*"|null), (\d+), (\d+), Saint\.FeastType\.\w+, (?:"(?:[^"\\]|\\.)*"|null), ', line)
        if not mt:
            continue
        key = f"{mt.group(2)}-{mt.group(3)}-{mt.group(1)}"
        if key not in ADD:
            continue
        lm = re.compile(r'(listOf\((.*?)\)|emptyList\(\))(, feminineNames = listOf\((.*?)\))?').match(line, mt.end())
        assert lm, key
        alt0, fem0 = parse_list(lm.group(2)), parse_list(lm.group(4))
        assert (set(alt0), set(fem0)) == web_before[key], ("Android differs from web", key, alt0, fem0)
        alt, fem = plan(key, alt0, fem0)
        new = f"listOf({lit(alt)})" + (f", feminineNames = listOf({lit(fem)})" if fem else "")
        lines[i] = line[:lm.start()] + new + line[lm.end():]
        touched = True
        done.add(key)
    if touched and WRITE:
        open(p, "w", encoding="utf-8").write("\n".join(lines))
assert done == set(ADD), ("Android missing", set(ADD) - done)

added = sum(len(set(a) - web_before[k][0]) for k, (a, f) in web_after.items())
print(("WROTE" if WRITE else "DRY RUN"), len(ADD), "saints,", added, "names added")
for k, (a, f) in sorted(web_after.items(), key=lambda t: [int(x) for x in t[0].split("-")[:2]]):
    new = [n for n in a if n not in web_before[k][0]]
    moved = [n for n in f if n in web_before[k][0] and n not in web_before[k][1]]
    print(f"  {k}: +{', '.join(new)}" + (f"  [now feminine: {', '.join(moved)}]" if moved else ""))
