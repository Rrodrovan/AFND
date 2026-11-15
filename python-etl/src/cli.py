"""Línea de comandos del ETL.

Ejemplos:
    python -m src.cli ingest --zone piloto --source all
    python -m src.cli ingest --zone piloto --source power --start 2020-01-01 --end 2020-12-31
    python -m src.cli ingest --zone piloto --source smap --grid 3 --timeout-min 180
    python -m src.cli sync --zone piloto            # solo lo nuevo desde la última fecha cargada
    python -m src.cli sync --zone piloto --dry-run  # muestra qué pediría, sin descargar ni escribir
    python -m src.cli sync --all-zones              # todas las zonas aprobadas (lo que corre a diario)

Fuentes: power (NASA POWER), smap, modis, landsat, landsat-modis (modis + landsat) y all (todas).
SMAP, MODIS y Landsat usan AppEEARS y requieren EARTHDATA_USERNAME / EARTHDATA_PASSWORD.
"""

from __future__ import annotations

import argparse
import os
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
        "--timeout-min", type=int, default=360,
        help="Minutos máximos de espera por cada tarea de AppEEARS (por defecto 120)",
    )

    sync = sub.add_parser(
        "sync", help="Trae solo los datos nuevos de cada fuente (pensado para correr a diario)"
    )
    sync.add_argument("--zone", default="piloto", help="Código de la zona (por defecto: piloto)")
    sync.add_argument("--all-zones", action="store_true", help="Todas las zonas aprobadas de la base de datos")
    sync.add_argument("--source", choices=SOURCES, default="all")
    sync.add_argument("--grid", type=int, default=3, help="Puntos por lado de la rejilla de muestreo")
    sync.add_argument("--timeout-min", type=int, default=360, help="Minutos máximos por tarea de AppEEARS")
    sync.add_argument("--dry-run", action="store_true", help="Solo muestra el plan; no descarga ni escribe")
    sync.add_argument("--today", type=date.fromisoformat, help=argparse.SUPPRESS)  # para pruebas

    metrics = sub.add_parser(
        "metrics", help="Calcula E1, E2 y E3 con los datos de NASA POWER ya cargados y guarda los resultados"
    )
    metrics.add_argument("--zone", default="piloto", help="Código de la zona (por defecto: piloto)")
    metrics.add_argument("--dry-run", action="store_true", help="Calcula y muestra un resumen; no escribe en la base")
    return parser


def run_metrics(args: argparse.Namespace) -> int:
    from src.load import postgres
    from src.metrics import strategies

    with postgres.connect() as conn:
        zone_id = postgres.find_zone_id(conn, args.zone)
        bbox = postgres.zone_bbox(conn, args.zone) if zone_id else None
        if zone_id is None or bbox is None:
            print(f"La zona '{args.zone}' no existe o no tiene caja definida.")
            return 1
        rows = postgres.load_climate_for_metrics(conn, zone_id)
        if not rows:
            print(f"La zona '{args.zone}' no tiene clima de NASA POWER cargado. Ejecuta primero: sync.")
            return 1
        lat = (bbox[1] + bbox[3]) / 2
        out = strategies.compute(
            strategies.climate_index(rows), lat, rows[-1]["date"], rows[0]["date"]
        )
        if not out:
            print("No hay suficientes ciclos completos de cultivo en la serie (se necesitan al menos 5 años).")
            return 1
        print(f"Zona '{args.zone}' (lat {lat:.2f}): {len(out)} resultados con la serie {rows[0]['date']} a {rows[-1]['date']}.")
        for r in out:
            if r["scenario"] == "normal" and r["indicator"].startswith("Rendimiento"):
                print(
                    f"  {r['crop']:<6} {r['strategy']}  rendimiento relativo (normal): "
                    f"{r['value_mid']:.1f} % [{r['value_min']:.1f} – {r['value_max']:.1f}]"
                )
        if args.dry_run:
            print("Simulación: no se escribió nada.")
            return 0
        written = postgres.replace_strategy_results(conn, zone_id, out)
        print(f"Guardados {written} resultados (los anteriores de esta zona se reemplazaron).")
    return 0


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


def build_specs(conn_holder, bbox, args, appeears_client):
    """Fuentes de una zona: cómo descargar, cargar y consultar cada una (`conn_holder()` da la conexión)."""
    from src import sync
    from src.ingest import landsat_modis, power, smap
    from src.load import postgres

    lat, lon = bbox_centroid(bbox)
    return {
        "power": sync.SourceSpec(
            sync.POLICIES["power"],
            lambda s, e: power.fetch_daily(lat, lon, s, e),
            lambda zid, rows: postgres.upsert_climate_daily(conn_holder(), zid, rows),
            lambda zid: postgres.latest_date(conn_holder(), zid, "power"),
        ),
        "smap": sync.SourceSpec(
            sync.POLICIES["smap"],
            lambda s, e: smap.fetch_soil_moisture(appeears_client(), bbox, s, e, args.grid),
            lambda zid, rows: postgres.upsert_soil_moisture(conn_holder(), zid, rows),
            lambda zid: postgres.latest_date(conn_holder(), zid, "smap"),
        ),
        "modis": sync.SourceSpec(
            sync.POLICIES["modis"],
            lambda s, e: landsat_modis.fetch_modis(appeears_client(), bbox, s, e, args.grid),
            lambda zid, rows: postgres.upsert_vegetation_index(conn_holder(), zid, rows),
            lambda zid: postgres.latest_date(conn_holder(), zid, "modis"),
        ),
        "landsat": sync.SourceSpec(
            sync.POLICIES["landsat"],
            lambda s, e: landsat_modis.fetch_landsat(appeears_client(), bbox, s, e, args.grid),
            lambda zid, rows: postgres.upsert_vegetation_index(conn_holder(), zid, rows),
            lambda zid: postgres.latest_date(conn_holder(), zid, "landsat"),
        ),
    }


def resolve_sync_zones(conn, args, env_bbox: "BBox | None") -> list[tuple[int | None, str, "BBox"]]:
    """Zonas a sincronizar: [(id | None, código, caja)]. id None = zona aún no creada (solo en --dry-run).

    --zone CODE   una zona; si PILOT_ZONE_BBOX está definida manda sobre la caja guardada (compatibilidad).
    --all-zones   todas las zonas aprobadas de la base. Si PILOT_ZONE_BBOX está definida, la zona
                  'piloto' se crea o actualiza primero desde ahí.
    """
    from src.load import postgres

    def upsert_from_env(code: str) -> tuple[int | None, str, "BBox"]:
        stored = postgres.zone_bbox(conn, code)
        if stored is not None and tuple(stored) != tuple(env_bbox):
            print(
                f"[{code}] AVISO: la caja de la zona cambió respecto a la guardada {tuple(stored)}. "
                "Los datos ya cargados corresponden a la caja anterior; bórralos si quieres series coherentes."
            )
        if args.dry_run:
            return postgres.find_zone_id(conn, code), code, env_bbox
        zone_id = postgres.ensure_zone(conn, code, code.capitalize(), env_bbox)
        conn.commit()
        return zone_id, code, env_bbox

    if not args.all_zones:
        if env_bbox is not None:
            return [upsert_from_env(args.zone)]
        stored = postgres.zone_bbox(conn, args.zone)
        if stored is None:
            raise RuntimeError(
                f"La zona '{args.zone}' no existe en la base. Define PILOT_ZONE_BBOX o apruébala desde la página."
            )
        return [(postgres.find_zone_id(conn, args.zone), args.zone, stored)]

    zones = []
    if env_bbox is not None:
        zones.append(upsert_from_env("piloto"))
    seen = {code for _, code, _ in zones}
    zones += [z for z in postgres.list_approved_zones(conn) if z[1] not in seen]
    return zones


def run_sync_command(args: argparse.Namespace) -> int:
    from src import sync
    from src.ingest import appeears, smap
    from src.load import postgres

    raw_bbox = os.environ.get("PILOT_ZONE_BBOX")
    env_bbox = load_pilot_bbox() if raw_bbox else None
    default_start, _ = load_date_range()
    today = args.today or date.today()

    client = None

    def appeears_client() -> "appeears.AppeearsClient":
        nonlocal client
        if client is None:
            user, password = load_earthdata_credentials()
            client = appeears.AppeearsClient(user, password, timeout_seconds=args.timeout_min * 60)
        return client

    failed: list[str] = []
    with postgres.connect() as conn:
        zones = resolve_sync_zones(conn, args, env_bbox)
        if not zones:
            print("No hay zonas aprobadas para sincronizar.")
        for zone_id, code, bbox in zones:
            print(f"=== Zona '{code}' caja {tuple(bbox)} ===")
            specs = build_specs(lambda: conn, bbox, args, appeears_client)
            chosen = [specs[key] for key in sync.SYNC_ORDER if key in expand_sources(args.source)]
            results = sync.run_sync(conn, zone_id, chosen, today, default_start, dry_run=args.dry_run)
            failed += [f"{code}/{r.source}" for r in results if r.status == "error"]

        if not args.dry_run and args.source in ("smap", "all"):
            _warn_if_newer_smap(appeears, smap)

    if failed:
        print(f"Fuentes con error: {', '.join(failed)}")
        return 1
    return 0


def _warn_if_newer_smap(appeears, smap) -> None:
    """Avisa (sin cambiar nada) si AppEEARS ya ofrece una versión más nueva del producto SMAP."""
    try:
        products = appeears.AppeearsClient("", "").list_products()
        newer = appeears.newer_product_versions(products, smap.PRODUCT)
    except Exception as exc:  # es solo un aviso: nunca debe hacer fallar la sincronización
        print(f"[SMAP] No se pudo comprobar si hay una versión más nueva: {exc}")
        return
    if newer:
        print(
            f"[SMAP] AVISO: hay una versión más nueva de {smap.PRODUCT.split('.')[0]}: {', '.join(newer)}. "
            "Revisa los nombres de las capas antes de actualizar src/ingest/smap.py."
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return run_ingest(args)
    if args.command == "sync":
        return run_sync_command(args)
    if args.command == "metrics":
        return run_metrics(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
