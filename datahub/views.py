from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Value, Q
from django.db.models.functions import Coalesce
import numpy as np
import csv
from io import BytesIO
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .forms import UploadDataForm, CustomerAggregateForm
from .models import DataBatch, CustomerAggregate, CreditOperation
from .services.importer import import_batch

from scoring.services import score_customer


@login_required
def upload_data(request):
    if request.method == "POST":
        form = UploadDataForm(request.POST, request.FILES)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.uploaded_by = request.user
            batch.status = "PENDING"
            batch.save()

            try:
                result = import_batch(batch)
                messages.success(request, f"Carga completada: loaded={result['loaded']} skipped={result['skipped']}")
                return redirect("batches")
            except Exception as e:
                batch.status = "FAILED"
                batch.errors_json = str(e)
                batch.save()
                messages.error(request, f"Error al cargar: {e}")
                return redirect("upload_data")
    else:
        form = UploadDataForm()

    return render(request, "datahub/upload.html", {"form": form})


@login_required
def batches(request):
    qs = DataBatch.objects.order_by("-uploaded_at")
    return render(request, "datahub/batches.html", {"batches": qs})


@login_required
def customers_list(request):
    qs = CustomerAggregate.objects.order_by("-updated_at")

    oficina = request.GET.get("oficina", "").strip()
    riesgo = request.GET.get("riesgo", "").strip()   # "1" / "0"
    active = request.GET.get("active", "").strip()   # "1" / "0"
    tipo_credito = request.GET.get("tipo_credito", "").strip()  # NUEVO

    categoria = request.GET.get("categoria", "").strip()  # NUEVO

    if oficina:
        qs = qs.filter(oficina=oficina)

    if active in ("0", "1"):
        qs = qs.filter(is_active=bool(int(active)))

    if tipo_credito:
        qs = qs.filter(tipo_credito__iexact=tipo_credito)

    if categoria:
        qs = qs.filter(calificacion_riesgo__iexact=categoria)

    return render(request, "datahub/customers_list.html", {
        "rows": qs,
        "filters": {
            "oficina": oficina,
            "active": active,
            "tipo_credito": tipo_credito,
            "categoria": categoria,
        }
    })


@login_required
def customer_detail(request, cliente):
    obj = get_object_or_404(CustomerAggregate, cliente=cliente)
    hist = obj.history.all()[:50]  # últimos 50
    return render(request, "datahub/customer_detail.html", {"c": obj})

from scoring.rules import classify_morosidad
from datahub.models import CustomerAggregateHistory
from datahub.services.history import snapshot_customer, diff_dicts

@login_required
def customer_edit(request, cliente):
    obj = get_object_or_404(CustomerAggregate, cliente=cliente)

    if request.method == "POST":
        before = snapshot_customer(obj)

        form = CustomerAggregateForm(request.POST, instance=obj)
        if form.is_valid():
            updated = form.save(commit=False)

            # Recalcular regla/tablas (según tu norma)
            # (Aquí debes tener ya tu classify_morosidad(...) y setear categoria_norma/nivel_norma)
            # updated.categoria_norma = ...
            # updated.nivel_norma = ...
            # updated.riesgo_actual = ...

            updated.save()

            # Recalcular y guardar scoring ML automáticamente (ya lo tienes)
            try:
                result = score_customer(updated)
                updated.ml_proba_last = float(result["proba_riesgo_alto"])
                updated.ml_pred_last = bool(result["pred_riesgo_alto"] == 1)
                updated.ml_scored_at = timezone.now()
                updated.ml_scored_by = request.user.username
                updated.save(update_fields=["ml_proba_last","ml_pred_last","ml_scored_at","ml_scored_by"])
            except Exception as e:
                messages.warning(request, f"Cliente guardado, pero falló el scoring ML: {e}")

            after = snapshot_customer(updated)
            diff = diff_dicts(before, after)

            # Solo guarda histórico si hubo cambios reales
            if diff:
                CustomerAggregateHistory.objects.create(
                    cliente=updated,
                    changed_by=request.user,
                    action="EDIT",
                    before_json=before,
                    after_json=after,
                    diff_json=diff,
                    notes="Edición desde formulario",
                )

            messages.success(request, "Cliente actualizado correctamente.")
            return redirect("customer_detail", cliente=updated.cliente)

        # si inválido, vuelve a renderizar el form con errores
        return render(request, "datahub/customer_edit.html", {"form": form, "c": obj})

    # GET
    form = CustomerAggregateForm(instance=obj)
    return render(request, "datahub/customer_edit.html", {"form": form, "c": obj})


@login_required
@require_POST
def customer_toggle_active(request, cliente):
    obj = get_object_or_404(CustomerAggregate, cliente=cliente)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, f"Estado actualizado: {'ACTIVO' if obj.is_active else 'INACTIVO'}")
    return redirect("customers_list")


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from scoring.rules import (
    classify_morosidad,
    adjust_probability_by_category,
    decision_final,   # opcional si lo usas en UI
)

from scoring.services import score_customer
from .models import CustomerAggregate, CustomerRiskHistory
def _cat_ui_to_db(cat_ui: str) -> str:
    # "A-2" -> "A2", "C-1" -> "C1", "D" -> "D"
    return (cat_ui or "").replace("-", "").strip().upper()


def _riesgo_from_categoria_db(cat_db: str) -> int:
    """
    Define qué categorías se consideran 'ALTO' según norma.
    Ajusta a tu política bancaria.
    """
    cat = (cat_db or "").upper()
    # Normal/Potencial = BAJO; Deficiente/D/E = ALTO (ejemplo razonable)
    if cat in ("C1", "C2", "D", "E"):
        return 1
    return 0


@login_required
def customer_score(request, cliente):
    try:
        obj = get_object_or_404(CustomerAggregate, cliente=cliente)

        # 1) Scoring ML crudo (0..1)
        result = score_customer(obj)
        proba_ml = float(result.get("proba_riesgo_alto", 0.0))
        pred_ml = int(result.get("pred_riesgo_alto", 0))

        # 2) Categoría por NORMA (tabla) según tipo_credito + días mora
        dias_mora = int(obj.max_dias_mora or 0)
        cat_ui, nivel = classify_morosidad(obj.tipo_credito, dias_mora)  # e.g. "A-2", "Riesgo Normal"
        cat_db = _cat_ui_to_db(cat_ui)                                   # e.g. "A2"

        # 3) Probabilidad final (ajustada por norma)
        proba_final = adjust_probability_by_category(proba_ml, cat_ui)   # retorna 0..1

        # 4) Riesgo norma (vigente) según categoría (prioritaria)
        riesgo_norma = _riesgo_from_categoria_db(cat_db)

        # 5) HISTORIAL solo si cambia categoría vigente
        old_cat = (obj.categoria_norma or "").upper()
        if cat_db and old_cat != cat_db:
            CustomerRiskHistory.objects.create(
                customer=obj,
                categoria_anterior=old_cat or None,
                categoria_nueva=cat_db,
                nivel=nivel or "",
                dias_mora=dias_mora,
                tipo_credito=obj.tipo_credito,
                proba_ml=proba_ml,
                proba_final=proba_final,
                pred_ml=(pred_ml == 1),
                created_by=request.user.username,
            )

        # 6) ESTADO VIGENTE (CustomerAggregate)
        obj.categoria_norma = cat_db
        obj.nivel_norma = nivel
        obj.riesgo_actual = bool(riesgo_norma)

        # Guardas FINAL (norma) para coherencia en UI y reportes
        obj.ml_proba_last = proba_final
        obj.ml_pred_last = bool(pred_ml == 1)
        obj.ml_scored_at = timezone.now()
        obj.ml_scored_by = request.user.username

        obj.save(update_fields=[
            "categoria_norma", "nivel_norma", "riesgo_actual",
            "ml_proba_last", "ml_pred_last", "ml_scored_at", "ml_scored_by"
        ])

        # 7) RESPUESTA UI (enriquecida)
        result.update({
            # norma/tablas
            "categoria_morosidad": cat_ui,            # "A-2" (UI)
            "nivel_morosidad": nivel,                # "Riesgo Normal"
            "categoria_morosidad_db": cat_db,         # "A2" (BD)
            "riesgo_norma": riesgo_norma,             # 0/1

            # probas
            "proba_ml": proba_ml,                     # 0..1
            "proba_final": proba_final,               # 0..1 ajustada

            # coherencia UI actual
            "riesgo_actual_regla": int(obj.riesgo_actual),  # ya es norma
            "calificacion_riesgo_contraste": obj.calificacion_riesgo,

            # auditoría scoring
            "ml_scored_at": obj.ml_scored_at.isoformat() if obj.ml_scored_at else None,
            "ml_scored_by": obj.ml_scored_by,
        })

        return JsonResponse(result, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import CreditOperation, CustomerRiskHistory

@login_required
def operations_list(request):
    username = request.user.username

    qs = (
        CustomerRiskHistory.objects
        .select_related("customer")
        .filter(created_by=username)          # SOLO el usuario logueado
        .order_by("-created_at")
    )

    return render(request, "datahub/operations_list.html", {
        "history_rows": qs,
    })


def _dataset_by_office():
    rows = (
        CustomerAggregate.objects
        .values("oficina")
        .annotate(
            total_clientes=Count("id"),
            clientes_activos=Count("id", filter=Q(is_active=True)),
            total_operaciones=Coalesce(Sum("n_operaciones"), Value(0)),
            mora_promedio=Coalesce(Avg("max_dias_mora"), Value(0.0)),
        )
        .order_by("oficina")
    )
    return [
        {
            "oficina": row["oficina"] or "SIN OFICINA",
            "total_clientes": row["total_clientes"],
            "clientes_activos": row["clientes_activos"],
            "total_operaciones": row["total_operaciones"],
            "mora_promedio": round(float(row["mora_promedio"] or 0), 2),
        }
        for row in rows
    ]


def _dataset_users_more_than_2_operations():
    operation_counts = {
        row["cliente"]: row["total"]
        for row in CreditOperation.objects.values("cliente").annotate(total=Count("id"))
    }

    rows = []
    for customer in CustomerAggregate.objects.all().order_by("cliente"):
        total_ops = customer.n_operaciones if customer.n_operaciones is not None else operation_counts.get(customer.cliente, 0)
        if total_ops > 2:
            rows.append({
                "cliente": customer.cliente,
                "oficina": customer.oficina,
                "tipo_credito": customer.tipo_credito,
                "total_operaciones": total_ops,
                "max_dias_mora": customer.max_dias_mora,
                "categoria_norma": customer.categoria_norma,
                "calificacion_riesgo": customer.calificacion_riesgo,
            })

    rows.sort(key=lambda item: (-item["total_operaciones"], item["cliente"]))
    return rows


def _dataset_by_category():
    rows = (
        CustomerAggregate.objects
        .values("categoria_norma", "calificacion_riesgo")
        .annotate(
            total_clientes=Count("id"),
            total_operaciones=Coalesce(Sum("n_operaciones"), Value(0)),
            saldo_promedio=Coalesce(Avg("saldo_total"), Value(0.0)),
        )
        .order_by("categoria_norma", "calificacion_riesgo")
    )
    result = []
    for row in rows:
        categoria = row["categoria_norma"] or row["calificacion_riesgo"] or "SIN CATEGORÍA"
        result.append({
            "categoria": categoria,
            "total_clientes": row["total_clientes"],
            "total_operaciones": row["total_operaciones"],
            "saldo_promedio": round(float(row["saldo_promedio"] or 0), 2),
        })
    return result


def _export_csv(report_title, columns, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{report_title}.csv"'
    writer = csv.writer(response)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(col, "") for col in columns])
    return response


def _export_xlsx(report_title, columns, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws.append(columns)
    for row in rows:
        ws.append([row.get(col, "") for col in columns])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{report_title}.xlsx"'
    return response


def _export_pdf(report_title, columns, rows):
    output = BytesIO()
    p = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    y = height - 40
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, report_title.replace("_", " ").title())
    y -= 20

    p.setFont("Helvetica", 8)
    header = " | ".join(columns)
    p.drawString(40, y, header[:140])
    y -= 12

    for row in rows:
        line = " | ".join(str(row.get(col, "")) for col in columns)
        p.drawString(40, y, line[:140])
        y -= 12
        if y <= 40:
            p.showPage()
            y = height - 40
            p.setFont("Helvetica", 8)

    p.save()
    output.seek(0)

    response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report_title}.pdf"'
    return response


def _build_report(report_type):
    if report_type == "oficinas":
        columns = ["oficina", "total_clientes", "clientes_activos", "total_operaciones", "mora_promedio"]
        rows = _dataset_by_office()
        title = "reporte_oficinas"
    elif report_type == "usuarios_operaciones":
        columns = ["cliente", "oficina", "tipo_credito", "total_operaciones", "max_dias_mora", "categoria_norma", "calificacion_riesgo"]
        rows = _dataset_users_more_than_2_operations()
        title = "reporte_usuarios_mas_2_operaciones"
    elif report_type == "categorias":
        columns = ["categoria", "total_clientes", "total_operaciones", "saldo_promedio"]
        rows = _dataset_by_category()
        title = "reporte_categorias"
    else:
        return None, None, None
    return title, columns, rows


@login_required
def reports(request):
    report_type = request.GET.get("report", "oficinas")
    output_format = request.GET.get("format", "")

    report_title, columns, rows = _build_report(report_type)
    if not report_title:
        messages.error(request, "Tipo de reporte no válido.")
        return redirect("reports")

    if output_format == "csv":
        return _export_csv(report_title, columns, rows)
    if output_format == "xlsx":
        return _export_xlsx(report_title, columns, rows)
    if output_format == "pdf":
        return _export_pdf(report_title, columns, rows)

    table_rows = [[row.get(col, "") for col in columns] for row in rows]

    return render(request, "datahub/reports.html", {
        "report_type": report_type,
        "columns": columns,
        "table_rows": table_rows,
        "report_options": [
            ("oficinas", "Por oficina"),
            ("usuarios_operaciones", "Usuarios con más de 2 operaciones"),
            ("categorias", "Por categorías"),
        ],
    })
