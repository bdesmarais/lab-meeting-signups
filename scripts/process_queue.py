#!/usr/bin/env python3
"""Apply queued web-form claims (ntfy topic) to the lab-meeting sign-up sheets.

Runs inside the scheduled GitHub Action. One presenter slot per meeting date.
Claims are applied in strict arrival order (ntfy server time, then message id);
processed.json records handled ids so replays are impossible. A person who
already holds a slot on a sheet is skipped (absorbs double-clicks).
"""
import json, re, urllib.request

TOPIC = "https://ntfy.sh/lab-signups-f82be3e70c4343e1"
SHEETS = {"methods": "METHODS.md", "applied": "APPLIED.md"}

def main():
    with urllib.request.urlopen(TOPIC + "/json?poll=1&since=all", timeout=30) as r:
        lines = r.read().decode().split("\n")
    done = set(json.load(open("processed.json"))["processed"])
    claims = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            if ev.get("event") != "message" or ev["id"] in done:
                continue
            c = json.loads(ev["message"])
            if c.get("type") in SHEETS and c.get("week") and c.get("name"):
                claims.append((ev["time"], ev["id"], c))
        except (ValueError, KeyError):
            continue
    claims.sort(key=lambda t: (t[0], t[1]))
    changed = False
    log = []
    for _, mid, c in claims:
        done.add(mid)
        path = SHEETS[c["type"]]
        name = re.sub(r"[|\n\r]", " ", c["name"]).strip()[:80]
        if not name:
            log.append(f"skip {mid}: empty name")
            continue
        sheet_txt = open(path).read()
        lines2 = sheet_txt.split("\n")
        if re.search(r"^\|.*\| *" + re.escape(name) + r"(?: \(|\s*\|)", sheet_txt, re.M):
            log.append(f"skip {mid}: {name} already holds a slot on {path}")
            continue
        found = applied = full = False
        for i, line in enumerate(lines2):
            if not line.startswith(f"| {c['week']} "):
                continue
            found = True
            cells = line.split("|")
            if cells[2].strip() == "OPEN":
                cells[2] = f" {name} "
                lines2[i] = "|".join(cells)
                applied = True
            else:
                full = True
            break
        if applied:
            open(path, "w").write("\n".join(lines2))
            changed = True
            log.append(f"applied {mid}: {c['week']} {c['type']} -> {name}")
        elif full:
            log.append(f"skip {mid}: {c['week']} {c['type']} already taken")
        elif found:
            log.append(f"skip {mid}: {c['week']} unexpected")
        else:
            log.append(f"skip {mid}: date {c['week']} not on {path}")
    json.dump({"processed": sorted(done)}, open("processed.json", "w"), indent=1)
    print("\n".join(log) if log else "no new claims")
    print("CHANGED" if (changed or claims) else "NOCHANGE")

if __name__ == "__main__":
    main()
