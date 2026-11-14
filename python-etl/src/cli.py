"""Línea de comandos del ETL.

Ejemplos:
    python -m src.cli ingest --zone piloto
    python -m src.cli ingest --zone piloto --source power --start 2020-01-01 --end 2020-12-31
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Sequence

from src.config import bbox_centroid, load_date_range, load_pilot_bbox

SOURCES = ("power", "smap", "landsat-modis", "all")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.cli", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Descarga datos de la NASA y los carga en la base de datos")
    ingest.add_argument("--zone", default="piloto", help="Código de la zona (por defecto: piloto)")
    ingest.add_argument("--source", choices=SOURCES, default="power")
    ingest.add_argument("--start", type=date.fromisoformat, help="Fecha inicial AAAA-MM-DD")
    ingest.add_argument("--end", type=date.fromisoformat, help="Fecha final AAAA-MM-DD")
    return parser


def run_ingest(args: argparse.Namespace) -> int:
    from src.ingest import landsat_modis, power, smap
    from src.load import postgres

    bbox = load_pilot_bbox()
    default_start, default_end = load_date_range()
    start, end = args.start or default_start, args.end or default_end
    lat, lon = bbox_centroid(bbox)

    with postgres.connect() as conn:
        zone_id = postgres.ensure_zone(conn, args.zone, args.zone.capitalize(), bbox)
        conn.commit()

        if args.source in ("power", "all"):
            print(f"[POWER] {start} -> {end} en ({lat:.3f}, {lon:.3f})")
            rows = power.fetch_daily(lat, lon, start, end)
            count = postgres.upsert_climate_daily(conn, zone_id, rows)
            print(f"[POWER] {count} días cargados en climate_daily")

        if args.source in ("smap", "all"):
            try:
                smap.fetch_soil_moisture(bbox, start, end)
            except NotImplementedError as exc:
                print(f"[SMAP] omitido: {exc}")

        if args.source in ("landsat-modis", "all"):
            try:
                landsat_modis.fetch_vegetation_index(bbox, start, end)
            except NotImplementedError as exc:
                print(f"[Landsat/MODIS] omitido: {exc}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return run_ingest(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
