from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

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
    riesgo = request.GET.get("riesgo", "").strip()  # "1" / "0"
    active = request.GET.get("active", "").strip()  # "1" / "0"

    if oficina:
        qs = qs.filter(oficina=oficina)
    if riesgo in ("0", "1"):
        qs = qs.filter(riesgo_actual=bool(int(riesgo)))
    if active in ("0", "1"):
        qs = qs.filter(is_active=bool(int(active)))

    return render(request, "datahub/customers_list.html", {"rows": qs})


@login_required
def customer_detail(request, cliente):
    obj = get_object_or_404(CustomerAggregate, cliente=cliente)
    return render(request, "datahub/customer_detail.html", {"c": obj})

from scoring.rules import classify_morosidad
@login_required
def customer_edit(request, cliente):
    obj = get_object_or_404(CustomerAggregate, cliente=cliente)

    if request.method == "POST":
        form = CustomerAggregateForm(request.POST, instance=obj)
        if form.is_valid():
            updated = form.save(commit=False)
            cat, nivel = classify_morosidad(updated.tipo_credito, updated.max_dias_mora)

            updated.categoria_morosidad = cat
            updated.nivel_morosidad = nivel

            # 1) regla determinística (mora)
            updated.riesgo_actual = cat in {"B-1","B-2","C-1","C-2","D","E"}
            updated.save()

            # 2) scoring ML AUTOMÁTICO (y persistencia)
            try:
                result = score_customer(updated)
                updated.ml_proba_last = float(result["proba_riesgo_alto"])
                updated.ml_pred_last = bool(result["pred_riesgo_alto"] == 1)
                updated.ml_scored_at = timezone.now()
                updated.ml_scored_by = request.user.username
                updated.save(update_fields=["ml_proba_last", "ml_pred_last", "ml_scored_at", "ml_scored_by"])
            except Exception as e:
                messages.warning(request, f"Cliente guardado, pero falló el scoring ML: {e}")

            messages.success(request, "Cliente actualizado correctamente.")
            return redirect("customer_detail", cliente=updated.cliente)

        # si no es válido, cae a render con errores
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


from scoring.rules import classify_morosidad, adjust_probability_by_category, decision_final
@login_required
def customer_score(request, cliente):
    try:
        obj = get_object_or_404(CustomerAggregate, cliente=cliente)

        # 1) Scoring ML crudo (0..1)
        result = score_customer(obj)
        proba_ml = float(result["proba_riesgo_alto"])
        threshold = float(result.get("threshold", 0.5))

        # 2) Regla TABLA (categoría/nivel por tipo crédito + días mora)
        cat, nivel = classify_morosidad(obj.tipo_credito, obj.max_dias_mora)

        # 3) Probabilidad final ajustada por categoría (piso)
        proba_final = float(adjust_probability_by_category(proba_ml, cat))
        pred_final = int(proba_final >= threshold)

        # 4) Decisión final (opcional pero útil)
        decision = decision_final(cat, proba_final, threshold_aprob=threshold)

        # 5) Guardar ÚLTIMO scoring en BD (guardar lo FINAL, no lo crudo)
        obj.ml_proba_last = proba_final
        obj.ml_pred_last = bool(pred_final == 1)
        obj.ml_scored_at = timezone.now()
        obj.ml_scored_by = request.user.username

        # Si también quieres alinear el "riesgo_actual" para que NO confunda:
        # (ALTO desde B-1 en adelante)
        obj.riesgo_actual = cat in {"B-1", "B-2", "C-1", "C-2", "D", "E"}

        obj.save(update_fields=[
            "ml_proba_last",
            "ml_pred_last",
            "ml_scored_at",
            "ml_scored_by",
            "riesgo_actual",
        ])

        # 6) Respuesta para el frontend
        payload = {
            # ML crudo (para mostrar en pequeño si quieres)
            "proba_ml": proba_ml,

            # Prob final (la que debe destacarse)
            "proba_final": proba_final,
            "pred_final": pred_final,
            "threshold": threshold,

            # Tabla
            "categoria_morosidad": cat,
            "nivel_morosidad": nivel,

            # Regla (alineada a tabla)
            "riesgo_actual_regla": 1 if obj.riesgo_actual else 0,

            # Contraste
            "calificacion_riesgo_contraste": obj.calificacion_riesgo,

            # Gobernanza
            "decision_final": decision,
            "ml_scored_at": obj.ml_scored_at.isoformat(),
            "ml_scored_by": obj.ml_scored_by,
        }

        return JsonResponse(payload, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def operations_list(request):
    qs = CreditOperation.objects.order_by("-created_at")[:2000]
    return render(request, "datahub/operations_list.html", {"rows": qs})
