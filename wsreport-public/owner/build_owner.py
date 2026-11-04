"""Дашборд власника We.Code: зведені дані по керівниках напрямів і комерції → набори даних (JSON-рядки).

Вхід: output/dash (нічна вивантажка wsreport.py), output/managers (wsmanagers.py) і список проєктів
дашборду менеджерів (JSON-масив документів {id, data: {name, manager, internal}}, як віддає ArtifactData list).
Вихід — папка з файлами: leaders.json, months.json, trend.json, managers.json, about.json.

Використання: python build_owner.py <dash_dir> <managers_dir> <projects.json> <out_dir> [snap.json]
snap.json (необов'язково) — документ snap/<YYYY-MM> дашборду менеджерів: закріплення проєктів на кінець місяця.

Керівники:
  Марина Васильєва — Fuel Solutions + BAS Solutions D&I (план «Fuel + Корп внедрение»)
  Анна Воропаєва — Mobile
  Світлана Степура — Customer Support
  Іван Губченко — BAS LCW (Вайкики)
  Наталя Свідрук — комерція: усі менеджери проєктів разом
Утилізація = години місяця на задачі, які вже в PAID\\CLOSE (або ⛔️Definitively closed), ÷ усі години місяця.
"""
import datetime as dt
import json
import os
import sys
from collections import defaultdict

LEADERS = [
    {"key": "marina", "leader": "Марина Васильєва", "area": "Fuel Solutions + BAS Solutions D&I",
     "depts": ["Fuel Solutions", "BAS Solutions D&I"], "plan": "Fuel + Корп внедрение"},
    {"key": "anna", "leader": "Анна Воропаєва", "area": "Mobile", "depts": ["Mobile"], "plan": "Mobile"},
    {"key": "svitlana", "leader": "Світлана Степура", "area": "Customer Support (ІТС)",
     "depts": ["Customer Support"], "plan": "ИТС (Customer Support)"},
    {"key": "lcw", "leader": "Іван Губченко", "area": "BAS LCW (Вайкики)", "depts": ["BAS LCW"], "plan": "BAS LCW (Вайкики)"},
]
COMMERCE = {"key": "natalia", "leader": "Свідрук Наталя", "area": "Комерція: усі менеджери проєктів"}
FROM = "2026-08"


def load(d, n):
    with open(os.path.join(d, n + ".json"), encoding="utf-8") as f:
        return json.load(f)


def r1(x):
    return None if x is None else round(float(x), 1)


def pct(a, b):
    return round(a / b * 100) if b else None


def main():
    dash_dir, mgr_dir, proj_path, out_dir = sys.argv[1:5]
    snap = json.load(open(sys.argv[5], encoding="utf-8")) if len(sys.argv) > 5 and os.path.isfile(sys.argv[5]) else {}
    snap = snap.get("data", snap).get("assign", {}) if snap else {}
    os.makedirs(out_dir, exist_ok=True)

    deps = load(dash_dir, "departments")
    plans = load(dash_dir, "plans")
    hist = load(dash_dir, "history")
    emps = load(dash_dir, "employees")
    cur = max(r["month"] for r in deps)
    today = max(r["date"] for r in hist)
    months_it = sorted({r["month"] for r in deps})

    tk = load(mgr_dir, "tasks")
    tasks = tk["tasks"]
    entries = load(mgr_dir, "entries")
    pm = load(mgr_dir, "pm").get("staff", {})
    msnap = load(mgr_dir, "months")

    docs = json.load(open(proj_path, encoding="utf-8")) if os.path.isfile(proj_path) else []
    if isinstance(docs, dict):
        docs = docs.get("documents") or docs.get("docs") or list(docs.values())
    assign, internal = {}, set()
    for x in docs:
        x = x.get("data", x) if isinstance(x, dict) else {}
        if not x.get("name"):
            continue
        if x.get("manager"):
            assign[x["name"]] = x["manager"]
        if x.get("internal"):
            internal.add(x["name"])
    managers = sorted(set(assign.values()))

    # ---- години й оплачене (PAID\CLOSE) по напрямах, з записів часу
    dep_of = {}
    for r in sorted(emps, key=lambda r: r["month"]):
        dep_of[r["employee"]] = r["department"]
    byid = {str(t["id"]): t for t in tasks}
    lab_d, paid_d = defaultdict(float), defaultdict(float)
    for tid, es in entries.items():
        t = byid.get(tid)
        for e in es:
            m, who, h = e[0][:7], e[1], float(e[2] or 0)
            d = dep_of.get(who)
            if not d or m < FROM:
                continue
            lab_d[(d, m)] += h
            if t and t.get("s") == "PAID":
                paid_d[(d, m)] += h
    all_months = sorted({m for (_, m) in lab_d} | set(months_it))
    all_months = [m for m in all_months if FROM <= m <= cur]

    dep_row = {(r["department"], r["month"]): r for r in deps}
    plan_row = {(r["plan"], r["month"]): r for r in plans}

    leaders, months_rows, trend = [], [], []
    prev = [m for m in months_it if m < cur]
    prev = prev[-1] if prev else None
    for L in LEADERS:
        def agg(m):
            rs = [dep_row[(d, m)] for d in L["depts"] if (d, m) in dep_row]
            if not rs:
                return None
            s = lambda k: sum(float(r.get(k) or 0) for r in rs)
            hrs = s("hours_mtd") or 1
            p = plan_row.get((L["plan"], m), {})
            return {
                "fact": s("counted_mtd"), "hours": s("hours_mtd"), "people": int(s("people")), "at_risk": int(s("at_risk")),
                "overdue": int(s("overdue")), "open": int(s("open_tasks")), "closed": int(s("closed_mtd")),
                "tails_h": s("old_open_hours") + s("old_done_hours"), "tails_done_h": s("old_done_hours"),
                "tails_n": int(s("old_open_tasks") + s("old_done_tasks")),
                "health": round(sum(float(r.get("health_index") or 0) * float(r.get("hours_mtd") or 0) for r in rs) / hrs),
                "plan": p.get("plan_hours"), "forecast": p.get("forecast"),
                "forecast_pct": round(p["forecast_progress"] * 100) if p.get("forecast_progress") is not None else None,
                "progress_pct": round(p["progress"] * 100) if p.get("progress") is not None else None,
            }
        def util(m):
            lab = sum(lab_d.get((d, m), 0) for d in L["depts"])
            pd = sum(paid_d.get((d, m), 0) for d in L["depts"])
            return lab, pd
        a, b = agg(cur), agg(prev) if prev else None
        lab, pd = util(cur)
        plab, ppd = util(prev) if prev else (0, 0)
        ft = sum(1 for r in emps if r["month"] == cur and r["department"] in L["depts"] and r.get("emp_type") == "FT")
        leaders.append({
            "key": L["key"], "leader": L["leader"], "area": L["area"], "kind": "direction",
            "plan": a["plan"], "fact": r1(a["fact"]), "forecast": r1(a["forecast"]), "forecast_pct": a["forecast_pct"],
            "prev_fact": r1(b["fact"]) if b else None, "prev_pct": b["progress_pct"] if b else None,
            "people": a["people"], "ft": ft, "at_risk": a["at_risk"], "overdue": a["overdue"], "open": a["open"],
            "closed": a["closed"], "health": a["health"],
            "tails_h": r1(a["tails_h"]), "tails_done_h": r1(a["tails_done_h"]), "tails_n": a["tails_n"],
            "prev_tails_h": r1(b["tails_h"]) if b else None,
            "paid_h": r1(pd), "util": pct(pd, lab), "prev_paid_h": r1(ppd), "prev_util": pct(ppd, plab),
        })
        for m in all_months:
            g = agg(m)
            lb, p_ = util(m)
            months_rows.append({"key": L["key"], "leader": L["leader"], "month": m,
                                "fact": r1(g["fact"]) if g else r1(lb), "plan": g["plan"] if g else None,
                                "pct": (g["forecast_pct"] if m == cur else g["progress_pct"]) if g else None,
                                "paid_h": r1(p_), "util": pct(p_, lb), "tails_h": r1(g["tails_h"]) if g else None,
                                "partial": m == cur})
        for day in sorted({r["date"] for r in hist if r["date"][:7] == cur}):
            rs = [r for r in hist if r["date"] == day and r.get("kind") == "department" and r.get("department") in L["depts"]]
            p = next((r for r in hist if r["date"] == day and r.get("kind") == "plan" and r.get("department") == L["plan"]), {})
            if not rs:
                continue
            s = lambda k: sum(float(r.get(k) or 0) for r in rs)
            trend.append({"key": L["key"], "leader": L["leader"], "date": day,
                          "forecast_pct": round(p["forecast_progress"] * 100) if p.get("forecast_progress") is not None else None,
                          "tails_h": r1(s("old_open_hours") + s("old_done_hours")), "overdue": int(s("overdue")),
                          "closed": int(s("closed_mtd"))})

    # ---- комерція: менеджери проєктів (як у дашборді менеджерів)
    def owner(p, m=None):
        if m and m < cur and snap and p in snap:
            return snap.get(p)
        return assign.get(p)
    ent = lambda t: entries.get(str(t["id"]), [])
    hm = lambda t, m: sum(float(e[2] or 0) for e in ent(t) if e[0][:7] == m)
    rows = []
    for mg in managers + [None]:
        own = [t for t in tasks if t.get("p") not in internal and owner(t.get("p")) == mg]
        tl = [t for t in own if t.get("cm", "") < cur and t.get("s") != "PAID"]
        lab = sum(v.get(cur, 0) for p, v in pm.items() if p not in internal and owner(p) == mg)
        paid = sum(hm(t, cur) for t in own if t.get("s") == "PAID")
        plab = sum(v.get(prev, 0) for p, v in pm.items() if p not in internal and owner(p, prev) == mg) if prev else 0
        ppaid = sum(hm(t, prev) for t in tasks if t.get("p") not in internal and owner(t.get("p"), prev) == mg and t.get("s") == "PAID") if prev else 0
        rows.append({"manager": mg or "Не закріплені", "projects": len({p for p in pm if p not in internal and owner(p) == mg}),
                     "tails_done_h": r1(sum(t.get("f") or 0 for t in tl if t.get("s") == "DONE")),
                     "tails_done_n": sum(1 for t in tl if t.get("s") == "DONE"),
                     "tails_testing_h": r1(sum(t.get("f") or 0 for t in tl if t.get("s") == "TESTING BY CLIENT")),
                     "tails_h": r1(sum(t.get("f") or 0 for t in tl)), "tails_n": len(tl),
                     "done_month_h": r1(sum(t.get("f") or 0 for t in own if t.get("cm") == cur and t.get("s") == "DONE")),
                     "labor_h": r1(lab), "paid_h": r1(paid), "util": pct(paid, lab), "prev_util": pct(ppaid, plab)})
    rows = [r for r in rows if r["manager"] != "Не закріплені" or r["labor_h"] or r["tails_h"]]
    tot = lambda k: sum(r[k] or 0 for r in rows)
    lab_t, paid_t = tot("labor_h"), tot("paid_h")
    plab_t = sum(v.get(prev, 0) for p, v in pm.items() if p not in internal) if prev else 0
    ppaid_t = sum(hm(t, prev) for t in tasks if t.get("p") not in internal and t.get("s") == "PAID") if prev else 0
    # хвости на кінець минулого місяця — зі знімка months.json
    prev_tails = None
    if prev and prev in msnap:
        sn = msnap[prev]
        prev_tails = r1(sum(v[2] or 0 for t in tasks for v in [sn.get(str(t["id"]))]
                            if v and t.get("p") not in internal and t.get("cm", "") < prev and v[0] != "PAID"))
    leaders.append({
        "key": COMMERCE["key"], "leader": COMMERCE["leader"], "area": COMMERCE["area"], "kind": "commerce",
        "plan": None, "fact": r1(lab_t), "forecast": None, "forecast_pct": None, "prev_fact": r1(plab_t), "prev_pct": None,
        "people": len(managers), "ft": None, "at_risk": None, "overdue": None, "open": None, "closed": None, "health": None,
        "tails_h": r1(tot("tails_h")), "tails_done_h": r1(tot("tails_done_h")), "tails_n": int(tot("tails_n")),
        "prev_tails_h": prev_tails,
        "paid_h": r1(paid_t), "util": pct(paid_t, lab_t), "prev_paid_h": r1(ppaid_t), "prev_util": pct(ppaid_t, plab_t),
        "unassigned": sum(1 for p in pm if p not in internal and not assign.get(p) and pm[p].get(cur)),
    })
    for m in all_months:
        lb = sum(v.get(m, 0) for p, v in pm.items() if p not in internal)
        pd = sum(hm(t, m) for t in tasks if t.get("p") not in internal and t.get("s") == "PAID")
        th = None
        if m in msnap and m != cur:
            sn = msnap[m]
            th = r1(sum(v[2] or 0 for t in tasks for v in [sn.get(str(t["id"]))]
                        if v and t.get("p") not in internal and t.get("cm", "") < m and v[0] != "PAID"))
        if m == cur:
            th = r1(tot("tails_h"))
        months_rows.append({"key": COMMERCE["key"], "leader": COMMERCE["leader"], "month": m, "fact": r1(lb), "plan": None,
                            "pct": None, "paid_h": r1(pd), "util": pct(pd, lb), "tails_h": th, "partial": m == cur})

    about = [{"date": today, "month": cur, "prev_month": prev, "generated": dt.datetime.now().isoformat(timespec="seconds"),
              "export": tk.get("generated") or ""}]
    for name, data in (("leaders", leaders), ("months", months_rows), ("trend", trend), ("managers", rows), ("about", about)):
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("керівників:", len(leaders), "· місяців:", len(all_months), "· менеджерів:", len(rows), "· дата:", today)


if __name__ == "__main__":
    main()
