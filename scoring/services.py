import os
import joblib
import pandas as pd
from functools import lru_cache
from django.conf import settings
from scoring.rules import classify_morosidad, adjust_probability_by_category, decision_final, cat_to_db


def _debug_print(*args):
    # Solo imprime si DEBUG=True
    if getattr(settings, "DEBUG", False):
        print(*args)


@lru_cache(maxsize=1)
def load_artifact():
    path = settings.ML_MODEL_PATH

    _debug_print("===================================")
    _debug_print(">>> ML_MODEL_PATH =", path)
    _debug_print(">>> ABSOLUTE PATH =", os.path.abspath(path))
    _debug_print(">>> EXISTS        =", os.path.exists(path))
    if os.path.exists(path):
        _debug_print(">>> SIZE (bytes)  =", os.path.getsize(path))
        _debug_print(">>> MTIME        =", os.path.getmtime(path))
    _debug_print("===================================")

    artifact = joblib.load(path)
    return artifact


def reload_artifact():
    """Útil si reemplazas el .joblib sin reiniciar el server."""
    load_artifact.cache_clear()
    return load_artifact()


def _expected_columns(pipeline):
    # sklearn >= 1.0 puede exponer feature_names_in_
    if hasattr(pipeline, "feature_names_in_"):
        return list(pipeline.feature_names_in_)

    # fallback: ColumnTransformer guarda columnas
    pre = pipeline.named_steps.get("preprocess")
    cols = []
    if pre is not None and hasattr(pre, "transformers"):
        for _, _, c in pre.transformers:
            if isinstance(c, list):
                cols.extend(c)
    return list(dict.fromkeys(cols))  # unique preserve order


def _to_str_or_none(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != "" else None


def score_customer(customer_obj):
    artifact = load_artifact()
    pipeline = artifact["pipeline"]

    # ==== 1) ML crudo (0..1) ====
    row = {
        "n_operaciones": customer_obj.n_operaciones,
        "n_vigentes": customer_obj.n_vigentes,
        "monto_total": customer_obj.monto_total,
        "saldo_total": customer_obj.saldo_total,
        "plazo_prom": customer_obj.plazo_prom,
        "tasa_prom": customer_obj.tasa_prom,
        "patrimonio_tec": customer_obj.patrimonio_tec,
        "antiguedad_max_dias": customer_obj.antiguedad_max_dias,
        "dias_hasta_ultimo_venc": customer_obj.dias_hasta_ultimo_venc,

        "oficina_mode": customer_obj.oficina,
        "tipo_credito_mode": customer_obj.tipo_credito,
        "garantia_mode": customer_obj.garantia,
        "sexo_mode": customer_obj.sexo,
    }

    df = pd.DataFrame([row])

    proba_ml = float(pipeline.predict_proba(df)[:, 1][0])  # 0..1
    threshold = float(artifact.get("threshold_proba", 0.5))
    pred_ml = int(proba_ml >= threshold)

    # ==== 2) Regla normativa por TABLA ====
    cat_ui, nivel = classify_morosidad(customer_obj.tipo_credito, customer_obj.max_dias_mora)
    cat_db = cat_to_db(cat_ui)  # A3, C1, etc.

    # ==== 3) Proba final ajustada por norma (si aplica) ====
    proba_final = float(adjust_probability_by_category(proba_ml, cat_ui))  # tu función acepta A-3, etc.
    pred_final = int(proba_final >= threshold)

    # ==== 4) Riesgo actual (norma manda) ====
    # Política mínima: C1/C2/D/E => ALTO, A/B => BAJO
    riesgo_norma = 1 if cat_db in ("C1","C2","D","E") else 0

    # ==== 5) Recomendación opcional ====
    decision = decision_final(cat_ui, proba_final, threshold_aprob=threshold)

    return {
        "proba_riesgo_alto": proba_ml,
        "pred_riesgo_alto": pred_final,           # usa final para UI
        "threshold": threshold,

        "categoria_morosidad": cat_ui,            # "C-1" (para UI)
        "categoria_morosidad_db": cat_db,         # "C1" (para DB)
        "nivel_morosidad": nivel,
        "proba_final": proba_final,               # 0..1
        "riesgo_norma": riesgo_norma,             # 0/1
        "decision": decision,
    }

    