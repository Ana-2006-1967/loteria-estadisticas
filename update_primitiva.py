#!/usr/bin/env python3
"""
update_primitiva.py — La Primitiva
Fase 2: añade dias_retraso y ventanas de tiempo
"""

import csv, json, os, requests
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

CSV_PATH  = Path("primitiva_historico.csv")
JSON_PATH = Path("estadisticas_primitiva.json")
API_KEY   = os.environ.get("LOTERIA_API_KEY", "")
API_URL   = "https://api.loteriasapi.com/api/v1/results/primitiva/latest"

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
                    "fecha":         row[0],
                    "numeros":       sorted([int(row[i]) for i in range(1,7)]),
                    "complementario":int(row[7]) if row[7] else 0,
                    "reintegro":     int(row[8]) if row[8] else 0
                })
            except: continue
    print(f"[CSV Prim] {len(sorteos)} sorteos")
    return sorteos

def obtener_ultimo():
    if not API_KEY: return None
    try:
        resp = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        fecha = data.get("date") or data.get("fecha") or ""
        nums  = data.get("numbers") or data.get("numeros") or []
        comp  = data.get("complementary") or data.get("complementario") or 0
        rein  = data.get("reintegro") or 0
        if not fecha or not nums: return None
        for fmt in ("%Y-%m-%d","%-d/%m/%Y","%d/%m/%Y"):
            try: fecha_norm = datetime.strptime(str(fecha),fmt).strftime("%-d/%m/%Y"); break
            except: continue
        else: fecha_norm = str(fecha)
        return {"fecha":fecha_norm,"numeros":sorted([int(n) for n in nums]),"complementario":int(comp),"reintegro":int(rein)}
    except Exception as e: print(f"[API] {e}"); return None

def añadir_si_nuevo(sorteos, nuevo):
    if nuevo is None: return sorteos
    if nuevo["fecha"] in {s["fecha"] for s in sorteos}: return sorteos
    sorteos.insert(0, nuevo)
    with open(CSV_PATH,"w",encoding="utf-8",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["FECHA","COMBINACIÓN GANADORA","","","","","","COMP.","R.","JOKER"])
        for s in sorteos:
            writer.writerow([s["fecha"]]+[str(x).zfill(2) for x in s["numeros"]]+[str(s["complementario"]).zfill(2),str(s["reintegro"]),""])
    return sorteos

def calcular_retraso_lista(sorteos, rango, campo):
    retraso = {}
    for n in rango:
        for i, s in enumerate(sorteos):
            if n in s[campo]: retraso[n] = i; break
        else: retraso[n] = len(sorteos)
    return retraso

def calcular_retraso_valor(sorteos, rango, campo):
    retraso = {}
    for n in rango:
        for i, s in enumerate(sorteos):
            if s[campo] == n: retraso[n] = i; break
        else: retraso[n] = len(sorteos)
    return retraso

def stats_lista(sorteos, rango, total, retraso_map, campo):
    cnt = Counter()
    for s in sorteos:
        for v in s[campo]: cnt[v] += 1
    result = []
    for n in rango:
        count = cnt.get(n,0)
        result.append({"numero":n,"frecuencia":count,"porcentaje":round(count/total*100,2) if total else 0,"dias_retraso":retraso_map.get(n,0)})
    return sorted(result, key=lambda x: x["frecuencia"], reverse=True)

def stats_valor(sorteos, rango, total, retraso_map, campo, key="numero"):
    cnt = Counter(s[campo] for s in sorteos)
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
    r_nums = range(1,50); r_rein = range(0,10); r_comp = range(1,50)
    ret_nums = calcular_retraso_lista(sorteos, r_nums, "numeros")
    ret_comp = calcular_retraso_valor(sorteos, r_comp, "complementario")
    ret_rein = calcular_retraso_valor(sorteos, r_rein, "reintegro")
    nums_stats = stats_lista(sorteos, r_nums, total, ret_nums, "numeros")
    comp_stats = stats_valor(sorteos, r_comp, total, ret_comp, "complementario")
    rein_stats = stats_valor(sorteos, r_rein, total, ret_rein, "reintegro", key="reintegro")
    v20 = calcular_ventana(sorteos, n_sorteos=20)
    v50 = calcular_ventana(sorteos, n_sorteos=50)
    v1a = calcular_ventana(sorteos, dias=365)
    return {
        "ultima_actualizacion":   datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_sorteos":          total,
        "fecha_primer_sorteo":    sorteos[-1]["fecha"],
        "fecha_ultimo_sorteo":    sorteos[0]["fecha"],
        "numeros":                nums_stats,
        "complementarios":        comp_stats[:10],
        "reintegros":             rein_stats,
        "top10_mas_frecuentes":   nums_stats[:10],
        "top10_menos_frecuentes": nums_stats[-10:][::-1],
        "ventanas": {
            "v20": {"sorteos":len(v20),"numeros":stats_lista(v20,r_nums,len(v20),ret_nums,"numeros")[:10]},
            "v50": {"sorteos":len(v50),"numeros":stats_lista(v50,r_nums,len(v50),ret_nums,"numeros")[:10]},
            "v1a": {"sorteos":len(v1a),"numeros":stats_lista(v1a,r_nums,len(v1a),ret_nums,"numeros")[:10]}
        }
    }

def guardar_json(stats):
    with open(JSON_PATH,"w",encoding="utf-8") as f: json.dump(stats,f,ensure_ascii=False,indent=2)
    print(f"[OK] {JSON_PATH} — {stats['total_sorteos']} sorteos")

if __name__ == "__main__":
    print("="*50+"\n  La Primitiva — Fase 2\n"+"="*50)
    s = leer_csv(); s = añadir_si_nuevo(s, obtener_ultimo())
    stats = calcular_estadisticas(s); guardar_json(stats)
    print("Listo!")
