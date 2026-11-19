#!/usr/bin/env python3
"""Genera assets/stats.svg con datos reales de la API de GitHub.

Lo corre la GitHub Action (.github/workflows/stats.yml) todos los días.
Uso local:
  GH_TOKEN=xxx GH_USER=TheChaliX python3 scripts/stats.py
  python3 scripts/stats.py --placeholder   # tarjeta vacía, sin red
"""
import datetime, html, json, os, sys, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "stats.svg")
IGNORE_LANGS = {"Roff"}  # lenguajes que no querés mostrar

W = 900
CARD, BG, INK, MUTED, LINE, ACC = "#10161D", "#0D1117", "#E6EAE7", "#8B949E", "#232B34", "#3FB27F"
GREENS = ["#1A2620", "#1F5A40", "#2C8A5E", "#3FB27F", "#7FD8A9"]
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"

QUERY = """query($u:String!){ user(login:$u){
  repositories(ownerAffiliations:[OWNER], privacy:PUBLIC, first:100){ totalCount
    nodes{ isFork languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } } }
  contributionsCollection{ totalCommitContributions totalPullRequestContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount } } } } } }"""


def fetch(user, token):
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": QUERY, "variables": {"u": user}}).encode())
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "profile-stats")
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    if "errors" in res:
        raise SystemExit(f"Error de la API: {res['errors']}")
    u = res["data"]["user"]
    cc = u["contributionsCollection"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        if repo["isFork"]:
            continue
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in IGNORE_LANGS:
                continue
            size, color = langs.get(name, (0, edge["node"]["color"]))
            langs[name] = (size + edge["size"], color or MUTED)
    return {
        "total": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "repos": u["repositories"]["totalCount"],
        "prs": cc["totalPullRequestContributions"],
        "weeks": [sum(d["contributionCount"] for d in w["contributionDays"])
                  for w in cc["contributionCalendar"]["weeks"]],
        "langs": langs,
    }


def t(x, y, s, size=15, fill=INK, w=400, mono=False, anchor="start", ls=0):
    f = MONO if mono else SANS
    return (f'<text x="{x}" y="{y}" font-family="{f}" font-size="{size}" font-weight="{w}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}">{html.escape(str(s))}</text>\n')


def render(d):
    H = 430
    o = t(40, 46, "07", 12, ACC, 600, True, ls=1) + t(72, 46, "ESTADÍSTICAS", 12, INK, 600, True, ls=2)
    o += t(214, 46, "/ GitHub stats", 12, MUTED, 400, True, ls=1)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y")
    o += t(W - 40, 46, f"actualizado {stamp}" if d else "se actualiza solo cada día", 11, MUTED, 400, True, anchor="end")
    o += f'<line x1="40" y1="62" x2="{W-40}" y2="62" stroke="{LINE}"/>\n'

    # números principales
    nums = [("total", "contribuciones", "último año"), ("commits", "commits", "último año"),
            ("repos", "repos públicos", "public repos"), ("prs", "pull requests", "último año")]
    cw = (W - 80 - 3 * 16) / 4
    for i, (k, es, en) in enumerate(nums):
        x = 40 + i * (cw + 16)
        o += f'<rect x="{x:.0f}" y="84" width="{cw:.0f}" height="96" rx="10" fill="{BG}" stroke="{LINE}"/>\n'
        o += t(x + 18, 130, f"{d[k]:,}".replace(",", ".") if d else "—", 32, INK, 700)
        o += t(x + 18, 154, es, 13, ACC, 600, True)
        o += t(x + 18, 170, en, 11, MUTED, 400, True)

    # lenguajes
    o += t(40, 216, "lenguajes / top languages", 12, MUTED, 500, True, ls=1)
    bx, by, bw = 40, 228, W - 80
    o += f'<clipPath id="lc"><rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5"/></clipPath>'
    o += f'<rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5" fill="{BG}" stroke="{LINE}"/>\n'
    if d and d["langs"]:
        tot = sum(s for s, _ in d["langs"].values())
        items = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])
        top = [(n, s / tot, c) for n, (s, c) in items[:5]]
        rest = sum(s for _, (s, _) in items[5:]) / tot
        if rest > 0:
            top.append(("Otros", rest, "#4B535D"))
        x, seg = bx, ""
        for n, p, c in top:
            seg += f'<rect x="{x:.1f}" y="{by}" width="{max(bw * p - 2, 1):.1f}" height="10" fill="{c}"/>'
            x += bw * p
        o += f'<g clip-path="url(#lc)">{seg}</g>\n'
        for i, (n, p, c) in enumerate(top):
            lx = 40 + (i % 3) * 280
            ly = 266 + (i // 3) * 24
            o += f'<circle cx="{lx + 5}" cy="{ly - 4}" r="4.5" fill="{c}"/>'
            o += t(lx + 18, ly, n, 13, INK, 600) + t(lx + 240, ly, f"{p * 100:.1f}%", 12, MUTED, 400, True, anchor="end")
    else:
        o += t(40, 266, "// aparecen después de la primera actualización", 12, MUTED, 400, True)

    # contribuciones por semana
    o += t(40, 330, "contribuciones por semana / weekly contributions · 12 meses", 12, MUTED, 500, True, ls=1)
    weeks = (d["weeks"][-52:] if d else [0] * 52)
    mx = max(weeks + [1])
    base, step = 404, (W - 80) / 52
    for i, v in enumerate(weeks):
        h = max(3, v / mx * 56)
        lvl = 0 if v == 0 else min(4, 1 + int(3.999 * v / mx))
        x = 40 + i * step
        o += f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{step - 4:.1f}" height="{h:.1f}" rx="2" fill="{GREENS[lvl]}"/>'
    o += "\n"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Estadísticas de GitHub de TheChaliX">
<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="{CARD}" stroke="{LINE}"/>
{o}</svg>'''


if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        data = None
    else:
        token, user = os.environ.get("GH_TOKEN"), os.environ.get("GH_USER", "TheChaliX")
        if not token:
            raise SystemExit("Falta GH_TOKEN (o usá --placeholder)")
        data = fetch(user, token)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(data))
    print("stats.svg generado", "(placeholder)" if data is None else "")
