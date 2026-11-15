"""Línea de comandos del ETL.

Ejemplos:
    python -m src.cli ingest --zone piloto --source all
    python -m src.cli ingest --zone piloto --source power --start 2020-01-01 --end 2020-12-31
    python -m src.cli ingest --zone piloto --source smap --grid 3 --timeout-min 180

Fuentes: power (NASA POWER), smap, modis, landsat, landsat-modis (modis + landsat) y all (todas).
SMAP, MODIS y Landsat usan AppEEARS y requieren EARTHDATA_USERNAME / EARTHDATA_PASSWORD.
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Sequence

from src.config import bbox_centroid, load_date_range, load_earthdata_credentials, load_pilot_bbox

SOURCES = ("power", "smap", "modis", "landsat", "landsat-modis", "all")
ALL_SOURCES = ("power", "smap", "modis", "landsat")


def expand_sources(choice: str) -> list[str]:
    if choice == "all":
        return list(ALL_SOURCES)
    if choice == "landsat-modis":
        return ["modis", "landsat"]
    return [choice]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.cli", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Descarga datos de la NASA y los carga en la base de datos")
    ingest.add_argument("--zone", default="piloto", help="Código de la zona (por defecto: piloto)")
    ingest.add_argument("--source", choices=SOURCES, default="all")
    ingest.add_argument("--start", type=date.fromisoformat, help="Fecha inicial AAAA-MM-DD")
    ingest.add_argument("--end", type=date.fromisoformat, help="Fecha final AAAA-MM-DD")
    ingest.add_argument(
        "--grid", type=int, default=3,
        help="Puntos por lado de la rejilla de muestreo en SMAP/MODIS/Landsat (3 = 9 puntos; 1 = solo el centro)",
    )
    ingest.add_argument(
        "--timeout-min", type=int, default=120,
        help="Minutos máximos de espera por cada tarea de AppEEARS (por defecto 120)",
    )
    return parser


def run_ingest(args: argparse.Namespace) -> int:
    from src.ingest import appeears, landsat_modis, power, smap
    from src.load import postgres

    bbox = load_pilot_bbox()
    default_start, default_end = load_date_range()
    start, end = args.start or default_start, args.end or default_end
    lat, lon = bbox_centroid(bbox)

    client = None

    def appeears_client() -> "appeears.AppeearsClient":
        nonlocal client
        if client is None:
            user, password = load_earthdata_credentials()
            client = appeears.AppeearsClient(user, password, timeout_seconds=args.timeout_min * 60)
        return client

    failures: list[str] = []
    with postgres.connect() as conn:
        zone_id = postgres.ensure_zone(conn, args.zone, args.zone.capitalize(), bbox)
        conn.commit()

        for source in expand_sources(args.source):
            try:
                if source == "power":
                    print(f"[POWER] {start} -> {end} en ({lat:.3f}, {lon:.3f})")
                    rows = power.fetch_daily(lat, lon, start, end)
                    print(f"[POWER] {postgres.upsert_climate_daily(conn, zone_id, rows)} días cargados en climate_daily")
                elif source == "smap":
                    print(f"[SMAP] {start} -> {end}, rejilla {args.grid}x{args.grid} (puede tardar)")
                    rows = smap.fetch_soil_moisture(appeears_client(), bbox, start, end, args.grid)
                    print(f"[SMAP] {postgres.upsert_soil_moisture(conn, zone_id, rows)} días cargados en soil_moisture")
                elif source == "modis":
                    print(f"[MODIS] {start} -> {end}, rejilla {args.grid}x{args.grid} (puede tardar)")
                    rows = landsat_modis.fetch_modis(appeears_client(), bbox, start, end, args.grid)
                    print(f"[MODIS] {postgres.upsert_vegetation_index(conn, zone_id, rows)} fechas cargadas en vegetation_index")
                elif source == "landsat":
                    print(f"[LANDSAT] {start} -> {end}, rejilla {args.grid}x{args.grid} (puede tardar)")
                    rows = landsat_modis.fetch_landsat(appeears_client(), bbox, start, end, args.grid)
                    print(f"[LANDSAT] {postgres.upsert_vegetation_index(conn, zone_id, rows)} fechas cargadas en vegetation_index")
            except Exception as exc:  # una fuente que falla no debe detener a las demás
                conn.rollback()
                failures.append(source)
                print(f"[{source.upper()}] ERROR: {exc}")

    if failures:
        print(f"Fuentes con error: {', '.join(failures)}")
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return run_ingest(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
