import os
import joblib
import pandas as pd
from functools import lru_cache
from django.conf import settings

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
    cols = _expected_columns(pipeline)

    # IMPORTANTE:
    # - max_dias_mora NO va al modelo (define regla)
    # - calificacion_riesgo NO va al modelo (contraste)
    row = {
        # numéricas/agregadas
        "n_operaciones": customer_obj.n_operaciones,
        "n_vigentes": customer_obj.n_vigentes,
        "monto_total": customer_obj.monto_total,
        "saldo_total": customer_obj.saldo_total,
        "plazo_prom": customer_obj.plazo_prom,
        "tasa_prom": customer_obj.tasa_prom,
        "patrimonio_tec": customer_obj.patrimonio_tec,
        "antiguedad_max_dias": customer_obj.antiguedad_max_dias,
        "dias_hasta_ultimo_venc": customer_obj.dias_hasta_ultimo_venc,

        # categóricas (a string para consistencia)
        "oficina_mode": _to_str_or_none(customer_obj.oficina),
        "tipo_credito_mode": _to_str_or_none(customer_obj.tipo_credito),
        "garantia_mode": _to_str_or_none(customer_obj.garantia),
        "sexo_mode": _to_str_or_none(customer_obj.sexo),
    }

    df = pd.DataFrame([row])

    # asegura columnas que espera el pipeline
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    proba = float(pipeline.predict_proba(df)[:, 1][0])
    thr = float(artifact.get("threshold_proba", 0.5))
    pred = int(proba >= thr)

    return {
        "proba_riesgo_alto": proba,
        "pred_riesgo_alto": pred,  # 1 alto, 0 bajo
        "threshold": thr,
        "target_definition": artifact.get("target_definition", ""),
    }
