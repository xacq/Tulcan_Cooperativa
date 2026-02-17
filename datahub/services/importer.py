import pandas as pd
import numpy as np
from django.db import transaction
from ..models import DataBatch, CustomerAggregate, CreditOperation

# ---------
# Helpers
# ---------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("\n", " ", regex=False)
    )
    return df

def read_to_df(uploaded_file) -> tuple[pd.DataFrame, str]:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        return df, "CSV"
    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)
        return df, "XLSX" if name.endswith(".xlsx") else "XLS"
    raise ValueError("Formato no soportado. Use CSV/XLS/XLSX.")

def filter_whitelist(df: pd.DataFrame, allowed: list[str]) -> pd.DataFrame:
    cols = [c for c in df.columns if c in allowed]
    return df[cols].copy()

def bool_riesgo_actual(max_dias_mora):
    try:
        return int(max_dias_mora) > 0
    except Exception:
        return False


# ---------
# Column whitelists (canónicos)
# ---------
ALLOWED_CUSTOMER = [
    "cliente", "oficina", "tipo_credito", "garantia", "sexo", "calificacion_riesgo",
    "n_operaciones", "n_vigentes", "monto_total", "saldo_total", "plazo_prom", "tasa_prom",
    "patrimonio_tec", "max_dias_mora", "antiguedad_max_dias", "dias_hasta_ultimo_venc",
]

ALLOWED_OPERATION = [
    "cliente", "oficina", "estado", "fecha_concesion", "fecha_vencimiento", "fecha_corte_base",
    "monto_otorgado", "saldo_total", "tipo_credito", "plazo", "tasa_interes", "garantia",
    "calificacion_riesgo", "dias_mora", "sexo", "patrimonio_tec",
]


# ---------
# Import entrypoint
# ---------
def import_batch(batch: DataBatch) -> dict:
    df, ftype = read_to_df(batch.file)
    df = normalize_columns(df)

    batch.file_type = ftype
    batch.source_columns_json = str(list(df.columns))

    if batch.load_mode == DataBatch.MODE_CUSTOMER:
        return _import_customer_agg(batch, df)
    else:
        return _import_operations(batch, df)


@transaction.atomic
def _import_customer_agg(batch: DataBatch, df: pd.DataFrame) -> dict:
    required = ["cliente", "max_dias_mora"]
    for r in required:
        if r not in df.columns:
            raise ValueError(f"Falta columna requerida: {r}")

    df = filter_whitelist(df, ALLOWED_CUSTOMER)
    batch.rows_total = len(df)

    loaded, skipped = 0, 0

    # upsert por cliente
    for _, row in df.iterrows():
        cliente = str(row.get("cliente", "")).strip()
        if not cliente or cliente.lower() == "nan":
            skipped += 1
            continue

        defaults = {k: (None if pd.isna(row.get(k)) else row.get(k)) for k in df.columns if k != "cliente"}
        max_mora = defaults.get("max_dias_mora", 0)
        defaults["riesgo_actual"] = bool_riesgo_actual(max_mora)
        defaults["batch"] = batch

        CustomerAggregate.objects.update_or_create(
            cliente=cliente,
            defaults=defaults
        )
        loaded += 1

    batch.rows_loaded = loaded
    batch.rows_skipped = skipped
    batch.status = "PROCESSED"
    batch.save()

    return {"loaded": loaded, "skipped": skipped}


@transaction.atomic
def _import_operations(batch: DataBatch, df: pd.DataFrame) -> dict:
    required = ["cliente"]
    for r in required:
        if r not in df.columns:
            raise ValueError(f"Falta columna requerida: {r}")

    df = filter_whitelist(df, ALLOWED_OPERATION)
    batch.rows_total = len(df)

    loaded, skipped = 0, 0

    # Inserta operaciones (MVP: create row by row; luego optimizamos bulk)
    for _, row in df.iterrows():
        cliente = str(row.get("cliente", "")).strip()
        if not cliente or cliente.lower() == "nan":
            skipped += 1
            continue

        op = CreditOperation(
            batch=batch,
            cliente=cliente,
            oficina=str(row.get("oficina", "") or ""),
            estado=str(row.get("estado", "") or ""),
            monto_otorgado=_num(row.get("monto_otorgado")),
            saldo_total=_num(row.get("saldo_total")),
            tipo_credito=str(row.get("tipo_credito", "") or ""),
            plazo=_int(row.get("plazo")),
            tasa_interes=_num(row.get("tasa_interes")),
            garantia=str(row.get("garantia", "") or ""),
            calificacion_riesgo=str(row.get("calificacion_riesgo", "") or ""),
            dias_mora=_int(row.get("dias_mora")),
            sexo=str(row.get("sexo", "") or ""),
            patrimonio_tec=_num(row.get("patrimonio_tec")),
        )
        # fechas si vienen (si no, queda null)
        for fcol, attr in [
            ("fecha_concesion", "fecha_concesion"),
            ("fecha_vencimiento", "fecha_vencimiento"),
            ("fecha_corte_base", "fecha_corte_base"),
        ]:
            if fcol in df.columns and not pd.isna(row.get(fcol)):
                try:
                    op.__dict__[attr] = pd.to_datetime(row.get(fcol)).date()
                except Exception:
                    pass

        op.save()
        loaded += 1

    batch.rows_loaded = loaded
    batch.rows_skipped = skipped
    batch.status = "PROCESSED"
    batch.save()

    return {"loaded": loaded, "skipped": skipped}


def _num(v):
    try:
        if pd.isna(v): return None
        return float(v)
    except Exception:
        return None

def _int(v):
    try:
        if pd.isna(v): return None
        return int(float(v))
    except Exception:
        return None
