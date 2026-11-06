"""Render assets/stats.svg (contributions, streaks, 12-week activity) in the pond style.

Usage: GH_TOKEN=... python3 scripts/stats.py <login> <out.svg>
       python3 scripts/stats.py --test
"""
import datetime as dt
import json
import os
import sys
import urllib.request


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "User-Agent": "pond-stats"},
    )
    body = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch_days(login):
    """Every calendar day since account creation as [(date, count)], oldest first."""
    created = gql("query($l:String!){user(login:$l){createdAt}}", {"l": login})["user"]["createdAt"]
    start = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    days = {}
    while start < now:
        end = min(start + dt.timedelta(days=364), now)
        data = gql(
            "query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t)"
            "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}",
            {"l": login, "f": start.isoformat(), "t": end.isoformat()},
        )
        for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        start = end
    return sorted(days.items())


def streaks(days):
    """Return (current, current_start, longest, longest_start, longest_end).

    Today with zero contributions does not break the current streak (the day is not over).
    """
    active = days[:-1] if days and days[-1][1] == 0 else days
    current, cur_start = 0, None
    for date, count in reversed(active):
        if not count:
            break
        current, cur_start = current + 1, date
    longest = run = 0
    l_start = l_end = run_start = None
    for date, count in days:
        if count:
            run_start = run_start if run else date
            run += 1
            if run > longest:
                longest, l_start, l_end = run, run_start, date
        else:
            run = 0
    return current, cur_start, longest, l_start, l_end


def fmt(date):
    d = dt.date.fromisoformat(date)
    return f"{d:%b} {d.day}"


def smooth_path(points):
    """Catmull-Rom spline through points as an SVG cubic path."""
    p = [points[0]] + points + [points[-1]]
    out = [f"M{p[1][0]:.1f},{p[1][1]:.1f}"]
    for i in range(1, len(p) - 2):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (x1 + (x2 - x0) / 6, y1 + (y2 - y0) / 6)
        c2 = (x2 - (x3 - x1) / 6, y2 - (y3 - y1) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {x2:.1f},{y2:.1f}")
    return " ".join(out)


def render(days):
    total = sum(c for _, c in days)
    current, cur_start, longest, l_start, l_end = streaks(days)
    recent = days[-84:]
    best_date, best = max(recent, key=lambda d: d[1])
    W, H = 860, 330
    x0, x1, base, top = 44, 816, 300, 222
    peak = max(best, 1)
    pts = [(x0 + i * (x1 - x0) / (len(recent) - 1), base - (base - top) * c / peak) for i, (_, c) in enumerate(recent)]
    line = smooth_path(pts)
    area = f"{line} L{x1},{base} L{x0},{base} Z"
    lx, ly = pts[-1]
    cur_range = f"{fmt(cur_start)} – today" if current else "start one today"
    since = dt.date.fromisoformat(days[0][0])

    def col(cx, value, label, sub, color="#ffffff", delay=0.0):
        return (
            f'<g class="in" style="animation-delay:{delay}s">'
            f'<text x="{cx}" y="98" text-anchor="middle" class="num" fill="{color}">{value}</text>'
            f'<text x="{cx}" y="128" text-anchor="middle" class="lbl">{label}</text>'
            f'<text x="{cx}" y="150" text-anchor="middle" class="sub">{sub}</text></g>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{total} contributions, current streak {current} days, longest streak {longest} days">
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .num {{ font-size: 46px; font-weight: 800; letter-spacing: -1px; }}
    .lbl {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; font-weight: 700; letter-spacing: 2.5px; fill: #5fd0de; }}
    .sub {{ font-size: 13px; fill: #6f93a1; }}
    .cap {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; letter-spacing: 1.5px; fill: #6f93a1; }}
    .in {{ animation: in .7s ease-out both; }}
    @keyframes in {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
    .draw {{ stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 2.4s .5s ease-out forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    .fade {{ animation: in 1.2s 1.4s ease-out both; }}
    @media (prefers-reduced-motion: reduce) {{ .in, .fade {{ animation: none; }} .draw {{ animation: none; stroke-dashoffset: 0; }} }}
  </style>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0d2a3b"/><stop offset="1" stop-color="#06141d"/></linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3fb6c9" stop-opacity="0.45"/><stop offset="1" stop-color="#3fb6c9" stop-opacity="0"/></linearGradient>
    <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#3fb6c9"/><stop offset="1" stop-color="#f2c14e"/></linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd98a"/><stop offset="1" stop-color="#f29a4a"/></linearGradient>
  </defs>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#bg)" stroke="#1d4a5e" stroke-width="2"/>
  <line x1="287" y1="44" x2="287" y2="154" stroke="#1d4a5e" stroke-width="1.5"/>
  <line x1="573" y1="44" x2="573" y2="154" stroke="#1d4a5e" stroke-width="1.5"/>
  {col(144, f"{total:,}", "CONTRIBUTIONS", f"since {since:%b %Y}", delay=0.1)}
  {col(430, current, "DAY STREAK", cur_range, color="url(#gold)", delay=0.25)}
  {col(716, longest, "LONGEST STREAK", f"{fmt(l_start)} – {fmt(l_end)}" if longest else "–", delay=0.4)}
  <g fill="none" stroke="#f2c14e">
    <circle cx="430" cy="82" r="38" stroke-width="1.5"><animate attributeName="r" values="38;60" dur="3s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.35;0" dur="3s" repeatCount="indefinite"/></circle>
  </g>
  <line x1="{x0}" y1="186" x2="{x1}" y2="186" stroke="#1d4a5e" stroke-width="1.5" stroke-dasharray="2 6"/>
  <text x="{x0}" y="210" class="cap">LAST 12 WEEKS</text>
  <text x="{x1}" y="210" text-anchor="end" class="cap">BEST DAY <tspan fill="#f2c14e" font-weight="700">{best}</tspan> · {fmt(best_date).upper()}</text>
  <path d="{area}" fill="url(#area)" class="fade"/>
  <path d="{line}" fill="none" stroke="url(#stroke)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" pathLength="1" class="draw"/>
  <g class="fade">
    <circle cx="{lx:.1f}" cy="{ly:.1f}" r="4.5" fill="#f2c14e"/>
    <circle cx="{lx:.1f}" cy="{ly:.1f}" r="4.5" fill="none" stroke="#f2c14e" stroke-width="1.5"><animate attributeName="r" values="4.5;14" dur="2s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.8;0" dur="2s" repeatCount="indefinite"/></circle>
  </g>
</svg>
'''


def self_test():
    d = lambda counts: [(f"2026-01-{i + 1:02d}", c) for i, c in enumerate(counts)]
    assert streaks(d([1, 1, 0, 2, 3, 0]))[:3] == (2, "2026-01-04", 2)  # today=0 keeps streak
    assert streaks(d([1, 1, 1, 0, 1, 1]))[::2] == (2, 3, "2026-01-03")
    assert streaks(d([0, 0, 0]))[0::2] == (0, 0, None)
    assert render(d([0, 3, 5, 0, 2])).startswith("<svg")
    print("ok")


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        self_test()
    else:
        svg = render(fetch_days(sys.argv[1]))
        with open(sys.argv[2], "w") as f:
            f.write(svg)
