#!/usr/bin/env python3
"""
update_stats.py — El Gordo de la Primitiva
Fase 2: añade dias_retraso por número y estadísticas por ventana de tiempo
"""

import csv, json, os, requests
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

CSV_PATH  = Path("gordo_historico.csv")
JSON_PATH = Path("estadisticas_gordo.json")
API_KEY   = os.environ.get("LOTERIA_API_KEY", "")
API_URL   = "https://api.loteriasapi.com/api/v1/results/gordo/latest"

def parse_fecha(s):
    for fmt in ("%d/%m/%Y", "%-d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(s.strip(), fmt)
        except: pass
    return None

def leer_csv():
    sorteos = []
    if not CSV_PATH.exists(): print(f"[ERROR] No se encuentra {CSV_PATH}"); return sorteos
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            row = [c.strip() for c in row]
            if len(row) < 7 or not row[0]: continue
            try:
                fecha = row[0]
                nums  = [int(row[i]) for i in range(1, 6)]
                clave = int(row[6])
                sorteos.append({"fecha": fecha, "numeros": sorted(nums), "clave": clave})
            except: continue
    print(f"[CSV] {len(sorteos)} sorteos cargados")
    return sorteos

def obtener_ultimo():
    if not API_KEY: print("[API] Sin key"); return None
    try:
        resp = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        fecha = data.get("date") or data.get("fecha") or data.get("draw_date","")
        nums  = data.get("numbers") or data.get("numeros") or []
        clave = data.get("key_number") or data.get("clave") or 0
        if not fecha or not nums: return None
        for fmt in ("%Y-%m-%d","%-d/%m/%Y","%d/%m/%Y"):
            try: fecha_norm = datetime.strptime(str(fecha),fmt).strftime("%-d/%m/%Y"); break
            except: continue
        else: fecha_norm = str(fecha)
        return {"fecha": fecha_norm, "numeros": sorted([int(n) for n in nums]), "clave": int(clave)}
    except Exception as e: print(f"[API] {e}"); return None

def añadir_si_nuevo(sorteos, nuevo):
    if nuevo is None: return sorteos
    if nuevo["fecha"] in {s["fecha"] for s in sorteos}:
        print(f"[API] Ya existe {nuevo['fecha']}"); return sorteos
    print(f"[API] Nuevo: {nuevo['fecha']}")
    sorteos.insert(0, nuevo)
    with open(CSV_PATH,"w",encoding="utf-8",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["FECHA","COMB. GANADORA","","","","","CLAVE / R"])
        for s in sorteos:
            writer.writerow([s["fecha"]]+[str(n).zfill(2) for n in s["numeros"]]+[str(s["clave"])])
    print(f"[CSV] Actualizado con {len(sorteos)} sorteos")
    return sorteos

def calcular_retraso(sorteos, rango_nums, campo="numeros"):
    """Calcula cuántos sorteos lleva cada número sin aparecer."""
    retraso = {}
    for n in rango_nums:
        retraso[n] = 0
        for i, s in enumerate(sorteos):
            vals = s[campo] if campo == "numeros" else [s[campo]]
            if n in vals:
                retraso[n] = i  # posición = sorteos desde la última aparición
                break
        else:
            retraso[n] = len(sorteos)  # nunca ha salido
    return retraso

def calcular_ventana(sorteos, n_sorteos=None, dias=None):
    """Filtra sorteos por ventana de tiempo o cantidad."""
    if n_sorteos:
        return sorteos[:n_sorteos]
    if dias:
        corte = datetime.now() - timedelta(days=dias)
        return [s for s in sorteos if parse_fecha(s["fecha"]) and parse_fecha(s["fecha"]) >= corte]
    return sorteos

def stats_numeros(sorteos, rango, total, retraso_map, campo="numeros"):
    cnt = Counter()
    for s in sorteos:
        vals = s[campo] if campo == "numeros" else [s[campo]]
        for v in vals: cnt[v] += 1
    result = []
    for n in rango:
        count = cnt.get(n, 0)
        result.append({
            "numero":       n,
            "frecuencia":   count,
            "porcentaje":   round(count / total * 100, 2) if total else 0,
            "dias_retraso": retraso_map.get(n, 0)
        })
    return sorted(result, key=lambda x: x["frecuencia"], reverse=True)

def calcular_estadisticas(sorteos):
    total = len(sorteos)
    if not total: return {}

    rango_nums  = range(1, 55)
    rango_clave = range(0, 10)

    retraso_nums  = calcular_retraso(sorteos, rango_nums, "numeros")
    retraso_clave = calcular_retraso(sorteos, rango_clave, "clave")

    nums_stats  = stats_numeros(sorteos, rango_nums,  total, retraso_nums,  "numeros")
    clave_stats = stats_numeros(sorteos, rango_clave, total, retraso_clave, "clave")

    # Ventanas de tiempo
    v20  = calcular_ventana(sorteos, n_sorteos=20)
    v50  = calcular_ventana(sorteos, n_sorteos=50)
    v1a  = calcular_ventana(sorteos, dias=365)
    # Histórico = sorteos completos

    return {
        "ultima_actualizacion":   datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_sorteos":          total,
        "fecha_primer_sorteo":    sorteos[-1]["fecha"],
        "fecha_ultimo_sorteo":    sorteos[0]["fecha"],
        "numeros":                nums_stats,
        "claves":                 clave_stats,
        "top10_mas_frecuentes":   nums_stats[:10],
        "top10_menos_frecuentes": nums_stats[-10:][::-1],
        "ventanas": {
            "v20": {
                "sorteos": len(v20),
                "numeros": stats_numeros(v20, rango_nums, len(v20), retraso_nums, "numeros")[:10]
            },
            "v50": {
                "sorteos": len(v50),
                "numeros": stats_numeros(v50, rango_nums, len(v50), retraso_nums, "numeros")[:10]
            },
            "v1a": {
                "sorteos": len(v1a),
                "numeros": stats_numeros(v1a, rango_nums, len(v1a), retraso_nums, "numeros")[:10]
            }
        }
    }

def guardar_json(stats):
    with open(JSON_PATH,"w",encoding="utf-8") as f:
        json.dump(stats,f,ensure_ascii=False,indent=2)
    print(f"[OK] {JSON_PATH} — {stats['total_sorteos']} sorteos")
    print(f"     Top3: {[x['numero'] for x in stats['top10_mas_frecuentes'][:3]]}")
    print(f"     Retraso top1: {stats['top10_mas_frecuentes'][0]['dias_retraso']} sorteos")

if __name__ == "__main__":
    print("="*55+"\n  El Gordo — Fase 2\n"+"="*55)
    sorteos = leer_csv()
    nuevo   = obtener_ultimo()
    sorteos = añadir_si_nuevo(sorteos, nuevo)
    stats   = calcular_estadisticas(sorteos)
    guardar_json(stats)
    print("="*55+"\n  Listo!\n"+"="*55)
