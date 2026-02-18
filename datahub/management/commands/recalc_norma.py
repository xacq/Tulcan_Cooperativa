from django.core.management.base import BaseCommand
from datahub.models import CustomerAggregate, CustomerRiskHistory
from scoring.services import score_customer

class Command(BaseCommand):
    help = "Recalcula categoria_norma/riesgo_actual para todos los clientes y guarda historial si cambia."

    def handle(self, *args, **options):
        qs = CustomerAggregate.objects.all().order_by("cliente")
        n = 0
        for obj in qs:
            result = score_customer(obj)
            new_cat = result.get("categoria_morosidad_db")
            if not new_cat:
                continue

            old_cat = obj.categoria_norma
            if old_cat != new_cat:
                CustomerRiskHistory.objects.create(
                    customer=obj,
                    categoria_anterior=old_cat,
                    categoria_nueva=new_cat,
                    nivel=result.get("nivel_morosidad") or "",
                    dias_mora=int(obj.max_dias_mora or 0),
                    tipo_credito=obj.tipo_credito,
                    proba_ml=float(result.get("proba_riesgo_alto") or 0.0),
                    proba_final=float(result.get("proba_final") or 0.0),
                    pred_ml=bool(int(result.get("pred_riesgo_alto") or 0) == 1),
                    created_by="system-backfill",
                )

            obj.categoria_norma = new_cat
            obj.nivel_norma = result.get("nivel_morosidad")
            obj.riesgo_actual = bool(int(result.get("riesgo_norma") or 0) == 1)
            obj.save(update_fields=["categoria_norma","nivel_norma","riesgo_actual"])
            n += 1

        self.stdout.write(self.style.SUCCESS(f"OK: recalculados {n} clientes"))
