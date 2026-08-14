#!/usr/bin/env python3
"""
update_stats.py
Proyecto Lotería Estadísticas - Ana Mª García Carralero
------------------------------------------------------
1. Lee el CSV histórico del Gordo de la Primitiva
2. Llama a la API de loteriasapi.com para obtener el último sorteo
3. Si es nuevo, lo añade al CSV
4. Calcula estadísticas de frecuencia
5. Genera estadisticas_gordo.json
"""

import csv
import json
import os
import requests
from datetime import datetime
from collections import Counter
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
CSV_PATH       = Path("gordo_historico.csv")
JSON_PATH      = Path("estadisticas_gordo.json")
API_KEY        = os.environ.get("LOTERIA_API_KEY", "")
API_URL        = "https://api.loteriasapi.com/api/v1/results/gordo/latest"

# ── 1. Leer CSV histórico ──────────────────────────────────────────────────────
def leer_csv():
    sorteos = []
    if not CSV_PATH.exists():
        print(f"[ERROR] No se encuentra {CSV_PATH}")
        return sorteos

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # saltar cabecera
        for row in reader:
            row = [c.strip() for c in row]
            if len(row) < 7 or not row[0]:
                continue
            try:
                fecha = row[0]
                nums  = [int(row[i]) for i in range(1, 6)]
                clave = int(row[6])
                sorteos.append({"fecha": fecha, "numeros": sorted(nums), "clave": clave})
            except (ValueError, IndexError):
                continue

    print(f"[CSV] {len(sorteos)} sorteos cargados desde {CSV_PATH}")
    return sorteos


# ── 2. Obtener último sorteo de la API ─────────────────────────────────────────
def obtener_ultimo_sorteo():
    if not API_KEY:
        print("[API] Sin API key — se omite consulta a la API")
        return None

    try:
        resp = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Adaptar según la estructura de respuesta de loteriasapi.com
        fecha  = data.get("date") or data.get("fecha") or data.get("draw_date", "")
        nums   = data.get("numbers") or data.get("numeros") or []
        clave  = data.get("key_number") or data.get("clave") or data.get("reintegro") or 0

        if not fecha or not nums:
            print("[API] Respuesta inesperada:", data)
            return None

        # Normalizar fecha a formato d/mm/yyyy
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(str(fecha), fmt)
                fecha_norm = dt.strftime("%-d/%m/%Y")
                break
            except ValueError:
                continue
        else:
            fecha_norm = str(fecha)

        return {"fecha": fecha_norm, "numeros": sorted([int(n) for n in nums]), "clave": int(clave)}

    except Exception as e:
        print(f"[API] Error al consultar la API: {e}")
        return None


# ── 3. Añadir sorteo nuevo al CSV si no existe ─────────────────────────────────
def añadir_si_nuevo(sorteos, nuevo):
    if nuevo is None:
        return sorteos

    fechas_existentes = {s["fecha"] for s in sorteos}
    if nuevo["fecha"] in fechas_existentes:
        print(f"[API] Sorteo del {nuevo['fecha']} ya existe en el CSV — sin cambios")
        return sorteos

    print(f"[API] Nuevo sorteo encontrado: {nuevo['fecha']} — añadiendo al CSV")
    sorteos.insert(0, nuevo)  # más reciente primero

    # Reescribir CSV
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["FECHA", "COMB. GANADORA", "", "", "", "", "CLAVE / R"])
        for s in sorteos:
            nums = s["numeros"]
            writer.writerow([s["fecha"]] + [str(n).zfill(2) for n in nums] + [str(s["clave"])])

    print(f"[CSV] Archivo actualizado con {len(sorteos)} sorteos")
    return sorteos


# ── 4. Calcular estadísticas ───────────────────────────────────────────────────
def calcular_estadisticas(sorteos):
    total = len(sorteos)
    if total == 0:
        return {}

    # Frecuencias de números (1–54)
    contador_nums  = Counter()
    contador_clave = Counter()

    for s in sorteos:
        for n in s["numeros"]:
            contador_nums[n] += 1
        contador_clave[s["clave"]] += 1

    # Construir ranking de números
    nums_stats = []
    for n in range(1, 55):
        count = contador_nums.get(n, 0)
        nums_stats.append({
            "numero":    n,
            "frecuencia": count,
            "porcentaje": round(count / total * 100, 2)
        })
    nums_stats.sort(key=lambda x: x["frecuencia"], reverse=True)

    # Ranking de claves (0–9)
    clave_stats = []
    for c in range(0, 10):
        count = contador_clave.get(c, 0)
        clave_stats.append({
            "clave":     c,
            "frecuencia": count,
            "porcentaje": round(count / total * 100, 2)
        })
    clave_stats.sort(key=lambda x: x["frecuencia"], reverse=True)

    # Top 10 y bottom 10
    top10    = nums_stats[:10]
    bottom10 = nums_stats[-10:][::-1]  # menos frecuentes primero

    # Fecha más antigua y más reciente
    fechas = [s["fecha"] for s in sorteos]

    return {
        "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_sorteos":        total,
        "fecha_primer_sorteo":  fechas[-1],
        "fecha_ultimo_sorteo":  fechas[0],
        "numeros":              nums_stats,
        "claves":               clave_stats,
        "top10_mas_frecuentes": top10,
        "top10_menos_frecuentes": bottom10
    }


# ── 5. Guardar JSON ────────────────────────────────────────────────────────────
def guardar_json(stats):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"[JSON] {JSON_PATH} generado correctamente")
    print(f"       Total sorteos: {stats['total_sorteos']}")
    print(f"       Último sorteo: {stats['fecha_ultimo_sorteo']}")
    print(f"       Top 3 números: {[x['numero'] for x in stats['top10_mas_frecuentes'][:3]]}")


# ── MAIN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  Proyecto Lotería Estadísticas — El Gordo")
    print(f"  Ejecutado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 55)

    sorteos   = leer_csv()
    nuevo     = obtener_ultimo_sorteo()
    sorteos   = añadir_si_nuevo(sorteos, nuevo)
    stats     = calcular_estadisticas(sorteos)
    guardar_json(stats)

    print("=" * 55)
    print("  ¡Listo!")
    print("=" * 55)
