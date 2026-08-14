#!/usr/bin/env python3
import csv, json, os, requests
from datetime import datetime
from collections import Counter
from pathlib import Path

CSV_PATH  = Path("euro_historico.csv")
JSON_PATH = Path("estadisticas_euro.json")
API_KEY   = os.environ.get("LOTERIA_API_KEY", "")
API_URL   = "https://api.loteriasapi.com/api/v1/results/euromillones/latest"

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
                fecha = row[0]
                nums  = [int(row[i]) for i in range(1, 6)]
                estrellas = [int(row[7]), int(row[8])]
                sorteos.append({"fecha": fecha, "numeros": sorted(nums), "estrellas": sorted(estrellas)})
            except (ValueError, IndexError): continue
    print(f"[CSV Euro] {len(sorteos)} sorteos cargados")
    return sorteos

def obtener_ultimo():
    if not API_KEY: print("[API] Sin key"); return None
    try:
        resp = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        fecha = data.get("date") or data.get("fecha") or data.get("draw_date","")
        nums  = data.get("numbers") or data.get("numeros") or []
        stars = data.get("stars") or data.get("estrellas") or []
        if not fecha or not nums: return None
        for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
            try: fecha_norm = datetime.strptime(str(fecha),fmt).strftime("%-d/%m/%Y"); break
            except: continue
        else: fecha_norm = str(fecha)
        return {"fecha": fecha_norm, "numeros": sorted([int(n) for n in nums]), "estrellas": sorted([int(s) for s in stars])}
    except Exception as e: print(f"[API] {e}"); return None

def añadir_si_nuevo(sorteos, nuevo):
    if nuevo is None: return sorteos
    if nuevo["fecha"] in {s["fecha"] for s in sorteos}: print(f"[API] Ya existe {nuevo['fecha']}"); return sorteos
    print(f"[API] Nuevo: {nuevo['fecha']}")
    sorteos.insert(0, nuevo)
    with open(CSV_PATH,"w",encoding="utf-8",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["FECHA","COMB. GANADORA","","","","","","ESTRELLAS",""])
        for s in sorteos:
            n = s["numeros"]; e = s["estrellas"]
            writer.writerow([s["fecha"]]+[str(x).zfill(2) for x in n]+[""]+[str(x).zfill(2) for x in e])
    return sorteos

def calcular(sorteos):
    total = len(sorteos)
    if not total: return {}
    cnt_nums = Counter()
    cnt_est  = Counter()
    for s in sorteos:
        for n in s["numeros"]: cnt_nums[n] += 1
        for e in s["estrellas"]: cnt_est[e] += 1
    nums_stats = sorted([{"numero":n,"frecuencia":cnt_nums.get(n,0),"porcentaje":round(cnt_nums.get(n,0)/total*100,2)} for n in range(1,51)], key=lambda x:-x["frecuencia"])
    est_stats  = sorted([{"estrella":e,"frecuencia":cnt_est.get(e,0),"porcentaje":round(cnt_est.get(e,0)/total*100,2)} for e in range(1,13)], key=lambda x:-x["frecuencia"])
    return {
        "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_sorteos": total,
        "fecha_primer_sorteo": sorteos[-1]["fecha"],
        "fecha_ultimo_sorteo": sorteos[0]["fecha"],
        "numeros": nums_stats,
        "estrellas": est_stats,
        "top10_mas_frecuentes": nums_stats[:10],
        "top10_menos_frecuentes": nums_stats[-10:][::-1],
        "top5_estrellas": est_stats[:5],
        "bottom5_estrellas": est_stats[-5:][::-1]
    }

if __name__ == "__main__":
    print("="*50+"\n  Euromillones Stats\n"+"="*50)
    s = leer_csv(); s = añadir_si_nuevo(s, obtener_ultimo())
    stats = calcular(s)
    with open(JSON_PATH,"w",encoding="utf-8") as f: json.dump(stats,f,ensure_ascii=False,indent=2)
    print(f"[OK] {JSON_PATH} — {stats['total_sorteos']} sorteos — Top3: {[x['numero'] for x in stats['top10_mas_frecuentes'][:3]]}")
