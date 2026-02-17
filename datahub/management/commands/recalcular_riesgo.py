from django.core.management.base import BaseCommand
from datahub.models import CustomerAggregate
from scoring.rules import classify_morosidad

class Command(BaseCommand):
    help = "Recalcula riesgo_actual usando la nueva tabla normativa"

    def handle(self, *args, **kwargs):
        total = 0
        cambios = 0

        for c in CustomerAggregate.objects.all():
            total += 1

            categoria, nivel = classify_morosidad(c.tipo_credito, c.max_dias_mora)

            nuevo_riesgo = categoria not in ("A-1","A-2","A-3")

            if c.riesgo_actual != nuevo_riesgo:
                c.riesgo_actual = nuevo_riesgo
                c.save(update_fields=["riesgo_actual"])
                cambios += 1

        self.stdout.write(self.style.SUCCESS(
            f"Clientes procesados: {total} | Actualizados: {cambios}"
        ))
