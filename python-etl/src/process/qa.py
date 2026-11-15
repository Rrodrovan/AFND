"""Control de calidad de los datos satelitales (máscaras de nubes y rangos válidos).

IMPORTANTE: las definiciones de bits provienen de las guías de usuario de MODIS (MOD13Q1 C6.1) y de
HLS v2.0. Confirmarlas en la documentación oficial antes de dar los resultados por definitivos.
"""

from __future__ import annotations

# Rangos válidos publicados por AppEEARS para estas capas
VI_MIN, VI_MAX = -0.2, 1.0  # NDVI / EVI
SOIL_MOISTURE_MIN, SOIL_MOISTURE_MAX = 0.0, 0.9  # m³/m³ (SPL4SMGP)
REFLECTANCE_MIN, REFLECTANCE_MAX = 0.0, 1.5
RAW_SCALE = 0.0001  # factor de escala de MODIS y HLS cuando el valor llega sin escalar


def modis_vi_quality_ok(qa: int) -> bool:
    """Capa `_250m_16_days_VI_Quality` de MOD13Q1.

    Acepta el píxel si:
      - bits 0-1 (MODLAND QA) valen 0 (buena calidad) o 1 (revisar otros QA), y
      - el bit 10 (nubes mezcladas) está apagado.
    """
    modland = qa & 0b11
    mixed_clouds = (qa >> 10) & 1
    return modland in (0, 1) and not mixed_clouds


def hls_fmask_ok(fmask: int) -> bool:
    """Capa `Fmask` de HLSL30.

    Rechaza el píxel si tiene nube (bit 1), adyacente a nube o sombra (bit 2) o sombra de nube (bit 3).
    Un valor de relleno (255) se rechaza también.
    """
    return (fmask & 0b1110) == 0


def clean_vegetation_index(value: float | None) -> float | None:
    """Devuelve NDVI/EVI en [-0.2, 1] o None. Si el valor llega sin escalar (p. ej. 5000), lo escala."""
    if value is None:
        return None
    if abs(value) > 1.5:
        value *= RAW_SCALE
    return value if VI_MIN <= value <= VI_MAX else None


def clean_reflectance(value: float | None) -> float | None:
    """Devuelve una reflectancia en [0, 1.5] o None. Si llega sin escalar, la escala."""
    if value is None:
        return None
    if abs(value) > 2:
        value *= RAW_SCALE
    return value if REFLECTANCE_MIN <= value <= REFLECTANCE_MAX else None


def clean_soil_moisture(value: float | None) -> float | None:
    if value is None:
        return None
    return value if SOIL_MOISTURE_MIN <= value <= SOIL_MOISTURE_MAX else None


def ndvi(nir: float | None, red: float | None) -> float | None:
    if nir is None or red is None or (nir + red) == 0:
        return None
    return clean_vegetation_index((nir - red) / (nir + red))


def evi(nir: float | None, red: float | None, blue: float | None) -> float | None:
    """EVI = 2.5 · (NIR − Rojo) / (NIR + 6·Rojo − 7.5·Azul + 1), con reflectancias en [0, 1]."""
    if nir is None or red is None or blue is None:
        return None
    denominator = nir + 6 * red - 7.5 * blue + 1
    if abs(denominator) < 1e-9:
        return None
    return clean_vegetation_index(2.5 * (nir - red) / denominator)
