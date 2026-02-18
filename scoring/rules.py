def _bucket_consumo_micro(d: int):
    if d <= 0: return ("A-1", "Riesgo Normal")
    if 1 <= d <= 15: return ("A-2", "Riesgo Normal")
    if 16 <= d <= 30: return ("A-3", "Riesgo Normal")
    if 31 <= d <= 45: return ("B-1", "Riesgo Potencial")
    if 46 <= d <= 60: return ("B-2", "Riesgo Potencial")
    if 61 <= d <= 75: return ("C-1", "Riesgo Deficiente")
    if 76 <= d <= 90: return ("C-2", "Riesgo Deficiente")
    if 91 <= d <= 120: return ("D", "Dudoso Recaudo")
    return ("E", "Pérdida")


def _bucket_vivienda(d: int):
    if d <= 0: return ("A-1", "Riesgo Normal")
    if 1 <= d <= 30: return ("A-2", "Riesgo Normal")
    if 31 <= d <= 60: return ("A-3", "Riesgo Normal")
    if 61 <= d <= 120: return ("B-1", "Riesgo Potencial")
    if 121 <= d <= 180: return ("B-2", "Riesgo Potencial")
    if 181 <= d <= 210: return ("C-1", "Riesgo Deficiente")
    if 211 <= d <= 270: return ("C-2", "Riesgo Deficiente")
    if 271 <= d <= 450: return ("D", "Dudoso Recaudo")
    return ("E", "Pérdida")


# scoring/rules.py
def cat_to_db(cat: str) -> str:
    # "A-3" -> "A3", "C-1" -> "C1"
    return (cat or "").replace("-", "").strip().upper()

def cat_to_ui(cat_db: str) -> str:
    # "A3" -> "A-3", "C1" -> "C-1", "D" -> "D"
    c = (cat_db or "").strip().upper()
    if len(c) == 2 and c[0] in "ABC" and c[1].isdigit():
        return f"{c[0]}-{c[1]}"
    return c



def _family(tipo_credito: str) -> str:
    """
    Normaliza la familia: CONSUMO_MICRO o VIVIENDA
    """
    tc = (tipo_credito or "").strip().upper()
    # Detecta vivienda por keywords (ajústalo si tus choices son exactos)
    if "VIV" in tc or "INMOB" in tc or "INTERES" in tc or "SOCIAL" in tc or "PUBLIC" in tc:
        return "VIVIENDA"
    return "CONSUMO_MICRO"


def classify_morosidad(tipo_credito: str, dias_mora: int):
    """
    Retorna (categoria, nivel)
    """
    d = int(dias_mora or 0)
    fam = _family(tipo_credito)
    if fam == "VIVIENDA":
        return _bucket_vivienda(d)
    return _bucket_consumo_micro(d)


def decision_final(categoria: str, proba_final: float, threshold_aprob: float = 0.5):
    """
    Política mínima (editable):
    - D/E: RECHAZAR (regla manda)
    - C-1/C-2: REVISIÓN
    - A/B: usar probabilidad final vs umbral
    """
    cat = (categoria or "").upper()
    p = float(proba_final or 0.0)

    if cat in ("D", "E"):
        return "RECHAZAR"
    if cat in ("C-1", "C-2"):
        return "REVISIÓN"
    return "APROBABLE" if p < threshold_aprob else "REVISIÓN"


def adjust_probability_by_category(proba_ml: float, categoria: str) -> float:
    """
    Ajuste por piso (floor) por categoría.
    Importante: no inventa riesgo; solo evita que ML contradiga norma.
    """
    floors = {
        "A-1": 0.00,
        "A-2": 0.05,
        "A-3": 0.10,
        "B-1": 0.25,
        "B-2": 0.35,
        "C-1": 0.60,
        "C-2": 0.75,
        "D": 0.90,
        "E": 1.00,
    }
    p = float(proba_ml or 0.0)
    floor = floors.get((categoria or "").upper(), 0.0)
    return max(p, floor)
