#!/usr/bin/env python3
"""
update_euro.py — Euromillones
Fase 2: añade dias_retraso y ventanas de tiempo
"""

import csv, json, os, requests
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

CSV_PATH  = Path("euro_historico.csv")
JSON_PATH = Path("estadisticas_euro.json")
API_KEY   = os.environ.get("LOTERIA_API_KEY", "")
API_URL   = "https://api.loteriasapi.com/api/v1/results/euromillones/latest"

def parse_fecha(s):
    for fmt in ("%d/%m/%Y","%-d/%m/%Y","%Y-%m-%d"):
        try: return datetime.strptime(s.strip(),fmt)
        except: pass
    return None

def leer_csv():
    sorteos = []
    if not CSV_PATH.exists(): return sorteos
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            row = [c.strip() for c in row]
            if len(row) < 9 or not row[0]: continue
            try:
                sorteos.append({
                    "fecha":    row[0],
                    "numeros":  sorted([int(row[i]) for i in range(1,6)]),
                    "estrellas":sorted([int(row[7]),int(row[8])])
                })
            except: continue
    print(f"[CSV Euro] {len(sorteos)} sorteos")
    return sorteos

def obtener_ultimo():
    if not API_KEY: return None
    try:
        resp = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        fecha = data.get("date") or data.get("fecha") or ""
        nums  = data.get("numbers") or data.get("numeros") or []
        stars = data.get("stars") or data.get("estrellas") or []
        if not fecha or not nums: return None
        for fmt in ("%Y-%m-%d","%-d/%m/%Y","%d/%m/%Y"):
            try: fecha_norm = datetime.strptime(str(fecha),fmt).strftime("%-d/%m/%Y"); break
            except: continue
        else: fecha_norm = str(fecha)
        return {"fecha":fecha_norm,"numeros":sorted([int(n) for n in nums]),"estrellas":sorted([int(s) for s in stars])}
    except Exception as e: print(f"[API] {e}"); return None

def añadir_si_nuevo(sorteos, nuevo):
    if nuevo is None: return sorteos
    if nuevo["fecha"] in {s["fecha"] for s in sorteos}: return sorteos
    sorteos.insert(0, nuevo)
    with open(CSV_PATH,"w",encoding="utf-8",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["FECHA","COMB. GANADORA","","","","","","ESTRELLAS",""])
        for s in sorteos:
            writer.writerow([s["fecha"]]+[str(x).zfill(2) for x in s["numeros"]]+[""]+[str(x).zfill(2) for x in s["estrellas"]])
    return sorteos

def calcular_retraso(sorteos, rango, campo):
    retraso = {}
    for n in rango:
        for i, s in enumerate(sorteos):
            vals = s[campo]
            if n in vals: retraso[n] = i; break
        else: retraso[n] = len(sorteos)
    return retraso

def stats_campo(sorteos, rango, total, retraso_map, campo, key="numero"):
    cnt = Counter()
    for s in sorteos:
        for v in s[campo]: cnt[v] += 1
    result = []
    for n in rango:
        count = cnt.get(n,0)
        result.append({key:n,"frecuencia":count,"porcentaje":round(count/total*100,2) if total else 0,"dias_retraso":retraso_map.get(n,0)})
    return sorted(result, key=lambda x: x["frecuencia"], reverse=True)

def calcular_ventana(sorteos, n_sorteos=None, dias=None):
    if n_sorteos: return sorteos[:n_sorteos]
    if dias:
        corte = datetime.now()-timedelta(days=dias)
        return [s for s in sorteos if parse_fecha(s["fecha"]) and parse_fecha(s["fecha"])>=corte]
    return sorteos

def calcular_estadisticas(sorteos):
    total = len(sorteos)
    if not total: return {}
    r_nums = range(1,51); r_est = range(1,13)
    ret_nums = calcular_retraso(sorteos, r_nums, "numeros")
    ret_est  = calcular_retraso(sorteos, r_est,  "estrellas")
    nums_stats = stats_campo(sorteos, r_nums, total, ret_nums, "numeros")
    est_stats  = stats_campo(sorteos, r_est,  total, ret_est,  "estrellas", key="estrella")
    v20 = calcular_ventana(sorteos, n_sorteos=20)
    v50 = calcular_ventana(sorteos, n_sorteos=50)
    v1a = calcular_ventana(sorteos, dias=365)
    return {
        "ultima_actualizacion":   datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_sorteos":          total,
        "fecha_primer_sorteo":    sorteos[-1]["fecha"],
        "fecha_ultimo_sorteo":    sorteos[0]["fecha"],
        "numeros":                nums_stats,
        "estrellas":              est_stats,
        "top10_mas_frecuentes":   nums_stats[:10],
        "top10_menos_frecuentes": nums_stats[-10:][::-1],
        "top5_estrellas":         est_stats[:5],
        "bottom5_estrellas":      est_stats[-5:][::-1],
        "ventanas": {
            "v20": {"sorteos":len(v20),"numeros":stats_campo(v20,r_nums,len(v20),ret_nums,"numeros")[:10]},
            "v50": {"sorteos":len(v50),"numeros":stats_campo(v50,r_nums,len(v50),ret_nums,"numeros")[:10]},
            "v1a": {"sorteos":len(v1a),"numeros":stats_campo(v1a,r_nums,len(v1a),ret_nums,"numeros")[:10]}
        }
    }

def guardar_json(stats):
    with open(JSON_PATH,"w",encoding="utf-8") as f: json.dump(stats,f,ensure_ascii=False,indent=2)
    print(f"[OK] {JSON_PATH} — {stats['total_sorteos']} sorteos")

if __name__ == "__main__":
    print("="*50+"\n  Euromillones — Fase 2\n"+"="*50)
    s = leer_csv(); s = añadir_si_nuevo(s, obtener_ultimo())
    stats = calcular_estadisticas(s); guardar_json(stats)
    print("Listo!")
