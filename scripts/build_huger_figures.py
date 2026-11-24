"""Static, publication-style figures for the Daniel Elliott Huger circle.

Outputs (PNG @300dpi + SVG) to figures/:
  huger_network      relationship network, edges read from unionism.db
  huger_timeline     event/place ledger for Huger, Petigru, Poinsett, Perry
"""
import sqlite3
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "unionism.db"
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

plt.rcParams["font.family"] = "serif"

REGION_COLOR = {"lowcountry": "#2f5d8a", "midlands": "#c47f2c", "upcountry": "#4f8a4b"}
NO_REGION = "#9a9a9a"

CORE = (94, 685, 3, 2)

# person_id -> (label, x, y)
NODES = {
    94: ("Daniel E.\nHuger", 0.0, 0.8),
    685: ("James L.\nPetigru", -5.0, -2.0),
    3: ("Joel R.\nPoinsett", 0.0, 4.6),
    2: ("Benjamin F.\nPerry", 5.0, -2.0),
    214: ("James\nChesnut", 1.9, -4.1),
    1443: ("Rene\nGoddard", -1.0, -4.1),
    5: ("William\nDrayton", -3.7, 2.9),
    4: ("Hugh\nLegaré", -8.6, 0.3),
    507: ("William J.\nGrayson", -8.6, -2.9),
    730: ("Thomas\nGrimké", -6.4, -5.2),
    21: ("Alfred\nHuger", -3.2, -5.2),
    832: ("James\nHamilton Jr.", -7.9, 3.4),
    684: ("Henry L.\nPinckney", 7.4, 1.6),
    272: ("John C.\nCalhoun", -9.0, -5.4),
}

SKIP = {(2, 832)}  # Perry–Hamilton "fractured" edge omitted to keep the figure legible

EDGE_LABEL = {
    "political_alliance": "alliance",
    "friendship": "friendship",
    "correspondence": "correspondence",
    "ideological_conflict": "conflict",
    "legal_connection": "legal",
    "co_mentioned": "co-mentioned in Perry letters",
}
RED = "#b03a2e"
NAVY = "#34495e"
GREY = "#999999"


def year(d):
    return str(d)[:4] if d else ""


def span(start, end):
    s, e = year(start), year(end)
    if s and e and s != e:
        return f"{s}–{e}"
    return s or e


def load_edges(con):
    ids = ",".join(str(i) for i in NODES)
    rows = con.execute(
        f"""SELECT person_low_id, person_high_id, relationship_type_code,
                   start_date, end_date, alignment_status_code, strength
            FROM relationships
            WHERE person_low_id IN ({ids}) AND person_high_id IN ({ids})
              AND relationship_type_code NOT LIKE 'kinship%'"""
    ).fetchall()
    best = {}
    for lo, hi, typ, s, e, al, st in rows:
        if lo not in CORE and hi not in CORE:
            continue
        if (lo, hi) in SKIP:
            continue
        if typ == "co_mentioned" and not (lo in CORE and hi in CORE):
            continue
        rank = (typ != "co_mentioned", al in ("adversarial", "fractured"), st or 0)
        cur = best.get((lo, hi))
        if cur is None or rank > cur["rank"]:
            best[(lo, hi)] = dict(rank=rank, type=typ, start=s, end=e, align=al, strength=st or 1)
    return best


def network(con):
    regions = dict(
        con.execute(
            f"SELECT person_id, home_region_sc_code FROM people WHERE person_id IN ({','.join(map(str, NODES))})"
        ).fetchall()
    )
    edges = load_edges(con)

    fig, ax = plt.subplots(figsize=(14, 9.6))
    ax.set_aspect("equal")
    ax.axis("off")

    for (lo, hi), e in edges.items():
        x1, y1 = NODES[lo][1:]
        x2, y2 = NODES[hi][1:]
        co = e["type"] == "co_mentioned"
        adv = e["align"] in ("adversarial", "fractured")
        color = RED if adv else (GREY if co else NAVY)
        style = (0, (1, 2.5)) if co else ("--" if adv else "-")
        lw = 1.5 if co else 1.0 + 1.1 * e["strength"]
        core_pair = lo in CORE and hi in CORE
        ax.plot([x1, x2], [y1, y2], color=color, linestyle=style, lw=lw, alpha=0.9 if core_pair else 0.55, zorder=1)
        if core_pair:
            label = EDGE_LABEL.get(e["type"], e["type"])
            sp = "" if co else span(e["start"], e["end"])
            if co:
                label = "co-mentioned\n(Perry letters)"
            elif sp:
                label += f"\n{sp}"
            t = 0.3 if {lo, hi} == {685, 2} else 0.5
            ax.text(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, label, fontsize=8, ha="center", va="center", color=color,
                    style="italic", zorder=2, linespacing=1.1,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.95))

    for pid, (label, x, y) in NODES.items():
        core = pid in CORE
        r = 1.0 if pid == 94 else (0.95 if core else 0.62)
        ax.add_patch(plt.Circle((x, y), r, fc=REGION_COLOR.get(regions.get(pid), NO_REGION),
                                ec="#d4a017" if pid == 94 else "white", lw=5 if pid == 94 else 1.5, zorder=3))
        ax.text(x, y, label, ha="center", va="center", color="white", zorder=4,
                fontsize=10.5 if core else 7.8, fontweight="bold" if core else "normal", linespacing=1.1)

    ax.annotate("Kibler (1946) calls Huger Perry's mentor;\nthe database codes only co-mentions (5 letters)",
                xy=(2.9, -0.95), xytext=(3.0, -3.7), fontsize=7.8, color="#555555", ha="left", va="center",
                style="italic", arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.8))

    ax.set_xlim(-10.2, 8.8)
    ax.set_ylim(-6.4, 5.9)
    fig.suptitle("Daniel Elliott Huger and the South Carolina Unionist Circle", fontsize=17, fontweight="bold", y=0.99)
    ax.set_title("Coded relationships among Huger, Petigru, Poinsett, Perry and their Unionist associates, 1809–1860",
                 fontsize=10.5, color="#444444", pad=0)

    leg = [
        Patch(fc=REGION_COLOR["lowcountry"], label="Lowcountry"),
        Patch(fc=REGION_COLOR["midlands"], label="Midlands"),
        Patch(fc=REGION_COLOR["upcountry"], label="Upcountry"),
        Patch(fc=NO_REGION, label="Region not coded"),
        Line2D([0], [0], color=NAVY, lw=2.8, label="Aligned (thicker = stronger)"),
        Line2D([0], [0], color=RED, lw=2, ls="--", label="Adversarial / fractured"),
        Line2D([0], [0], color=GREY, lw=1.5, ls=(0, (1, 2.5)), label="Co-mention only"),
    ]
    fig.legend(handles=leg, loc="lower center", ncol=7, fontsize=8.5, frameon=False, bbox_to_anchor=(0.5, 0.025))
    fig.text(0.5, 0.012,
             "Source: UnionismNetwork database (relationships); Pease & Pease 1995; Neumann; Kibler 1946; Carson 1920; "
             "B. F. Perry letters corpus. Only edges touching the four central figures are shown.",
             ha="center", fontsize=7.5, color="#666666")
    return fig


NS = "not specified"
EVENTS = [
    # (date label, sort key, event, place, {person_id: 'full'|'mention'})
    ("1809–10", 1809, "Huger befriends Petigru, a young teacher at Eutaw; later secures his Beaufort College post",
     "Eutaw", {94: "full", 685: "full"}),
    ("1828–30", 1828, "Huger–Poinsett Unionist alliance (Neumann, 33)", NS, {94: "full", 3: "full"}),
    ("1830", 1830.5, "Union Party city-council ticket against the Hayne–Hamilton Nullifier ticket", "Charleston",
     {94: "full", 685: "full"}),
    ("Nov 1830", 1830.9, "Huger leads Union Party resistance in the SC lower house; defends Rene Goddard", "Columbia",
     {94: "full"}),
    ("1831", 1831, "Unionist Boarding House during the legislative session (with William Elliott)", "Columbia",
     {94: "full", 685: "full", 3: "full"}),
    ("Oct 1832", 1832.8, "Union HQ election violence: Petigru and Poinsett struck", "Charleston",
     {685: "full", 3: "full"}),
    ("14 Dec 1832", 1832.95, "Remonstrance and Protest signed at the SC Union Convention", "Columbia",
     {94: "full", 685: "full", 3: "full", 2: "full"}),
    ("1833", 1833.3, "Independent Ticket: Unionists and disaffected Nullifiers", NS, {94: "full", 685: "full"}),
    ("1833–34", 1833.8, "Petigru and Grimké co-counsel in McCready v. Hunt against the Test Oath", "SC Ct. of Appeals",
     {685: "full"}),
    ("Mar 1834", 1834.2, "SC Union Convention: Huger serves as President", "Greenville", {94: "full"}),
    ("1836", 1836, "United Ticket (anti-Pinckney): Poinsett nominee, Petigru candidate", "Charleston",
     {685: "full", 3: "full"}),
    ("Dec 1842", 1842.9, "Perry writes to Elizabeth Perry (letters 5–6), naming Huger", "Columbia",
     {2: "full", 94: "mention"}),
    ("Apr 1852", 1852.3, "Perry writes to Anna Perry (letter 184), naming Huger", "Columbia",
     {2: "full", 94: "mention"}),
    ("Aug 1854", 1854.6, "Huger dies, ending a 44-year alliance with Petigru", "—", {94: "full", 685: "mention"}),
    ("Dec 1860", 1860.95, "SC Secession Convention; Petigru and Perry coded as opposing secession", "Columbia",
     {685: "full", 2: "full"}),
]

PLACE_COLOR = {"Charleston": "#2f5d8a", "Columbia": "#c47f2c", "Greenville": "#4f8a4b", "Eutaw": "#7b5ea7"}


def timeline():
    events = sorted(EVENTS, key=lambda e: e[1])
    cols = [(94, "Huger"), (685, "Petigru"), (3, "Poinsett"), (2, "Perry")]
    n = len(events)
    fig, ax = plt.subplots(figsize=(14, 9.4))
    ax.set_xlim(-0.6, 13.6)
    ax.set_ylim(n - 0.3, -2.0)
    ax.axis("off")

    colx = {pid: 7.9 + i * 1.0 for i, (pid, _) in enumerate(cols)}
    for pid, name in cols:
        ax.text(colx[pid], -1.0, name, ha="center", va="center", fontsize=10.5, fontweight="bold")
        ax.plot([colx[pid]] * 2, [-0.45, n - 0.55], color="#dddddd", lw=1, zorder=0)
    ax.text(-0.5, -1.0, "Date", fontsize=10.5, fontweight="bold", va="center")
    ax.text(1.5, -1.0, "Event", fontsize=10.5, fontweight="bold", va="center")
    ax.text(11.6, -1.0, "Place", fontsize=10.5, fontweight="bold", va="center")
    ax.plot([-0.5, 13.6], [-0.5, -0.5], color="#333333", lw=1)

    for i, (d, _, ev, place, who) in enumerate(events):
        if i % 2 == 0:
            ax.axhspan(i - 0.5, i + 0.5, color="#f5f5f2", zorder=-1)
        ax.text(-0.5, i, d, va="center", fontsize=9.2, fontweight="bold")
        ax.text(1.5, i, "\n".join(textwrap.wrap(ev, 66)), va="center", fontsize=8.6, linespacing=1.15)
        for pid, kind in who.items():
            ax.scatter([colx[pid]], [i], s=120, zorder=3, facecolor=NAVY if kind == "full" else "white",
                       edgecolor=NAVY, linewidths=1.6)
        ax.text(11.6, i, place, va="center", fontsize=8.8, color=PLACE_COLOR.get(place, "#777777"), fontweight="bold")

    ax.set_title("Huger, Petigru, Poinsett and Perry: Events and Places", fontsize=16, fontweight="bold", pad=10)
    leg = [
        Line2D([0], [0], marker="o", color="w", mfc=NAVY, mec=NAVY, ms=9, label="Documented participant / coded position"),
        Line2D([0], [0], marker="o", color="w", mfc="white", mec=NAVY, ms=9, label="Named or mentioned only"),
    ]
    fig.legend(handles=leg, loc="lower center", ncol=2, fontsize=8.8, frameon=False, bbox_to_anchor=(0.5, 0.035))
    fig.text(0.5, 0.015,
             "Source: UnionismNetwork database (events, positions, relationships, person_organization); Pease & Pease 1995; "
             "Neumann; Carson 1920; B. F. Perry letters. 'Not specified' = place not coded in the database.",
             ha="center", fontsize=7.5, color="#666666")
    return fig


def main():
    con = sqlite3.connect(DB)
    for name, fig in (("huger_network", network(con)), ("huger_timeline", timeline())):
        fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", facecolor="white")
        fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print("wrote", OUT / f"{name}.png")


if __name__ == "__main__":
    main()
