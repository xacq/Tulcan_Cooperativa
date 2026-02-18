def snapshot_customer(obj):
    """
    Campos relevantes que quieres auditar.
    Ajusta esta lista a tu criterio.
    """
    return {
        "oficina": obj.oficina,
        "tipo_credito": obj.tipo_credito,
        "garantia": obj.garantia,
        "sexo": obj.sexo,

        "n_operaciones": obj.n_operaciones,
        "n_vigentes": obj.n_vigentes,
        "monto_total": float(obj.monto_total or 0),
        "saldo_total": float(obj.saldo_total or 0),
        "plazo_prom": float(obj.plazo_prom or 0),
        "tasa_prom": float(obj.tasa_prom or 0),
        "patrimonio_tec": float(obj.patrimonio_tec or 0),
        "antiguedad_max_dias": obj.antiguedad_max_dias,
        "dias_hasta_ultimo_venc": obj.dias_hasta_ultimo_venc,
        "max_dias_mora": obj.max_dias_mora,

        # regla/tablas
        "riesgo_actual": bool(obj.riesgo_actual),
        "categoria_norma": getattr(obj, "categoria_norma", None),
        "nivel_norma": getattr(obj, "nivel_norma", None),

        # scoring ML último
        "ml_proba_last": float(obj.ml_proba_last) if obj.ml_proba_last is not None else None,
        "ml_pred_last": bool(obj.ml_pred_last) if obj.ml_pred_last is not None else None,
        "ml_scored_at": obj.ml_scored_at.isoformat() if getattr(obj, "ml_scored_at", None) else None,
        "ml_scored_by": getattr(obj, "ml_scored_by", None),
    }


def diff_dicts(before, after):
    changes = {}
    before = before or {}
    after = after or {}
    keys = set(before.keys()) | set(after.keys())
    for k in sorted(keys):
        if before.get(k) != after.get(k):
            changes[k] = {"from": before.get(k), "to": after.get(k)}
    return changes
