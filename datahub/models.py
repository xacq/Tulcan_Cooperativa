from django.db import models
from django.contrib.auth.models import User

class DataBatch(models.Model):
    MODE_CUSTOMER = "CUSTOMER_AGG"
    MODE_OPERATION = "OPERATION"

    MODE_CHOICES = [
        (MODE_CUSTOMER, "Agregado por cliente"),
        (MODE_OPERATION, "Por operación"),
    ]

    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    file = models.FileField(upload_to="uploads/")
    file_type = models.CharField(max_length=10, default="")  # CSV/XLS/XLSX
    load_mode = models.CharField(max_length=20, choices=MODE_CHOICES)

    status = models.CharField(max_length=20, default="PENDING")  # PROCESSED/FAILED
    rows_total = models.IntegerField(default=0)
    rows_loaded = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)

    errors_json = models.TextField(blank=True, default="")
    source_columns_json = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Batch {self.id} ({self.load_mode}) - {self.status}"


class CustomerAggregate(models.Model):
    batch = models.ForeignKey(DataBatch, null=True, blank=True, on_delete=models.SET_NULL)

    SEX_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("O", "Otro/No declara"),
    ]

    TIPO_CREDITO_CHOICES = [
        ("CONSUMO", "Consumo"),
        ("MICROCREDITO", "Microcrédito"),
        ("COMERCIAL", "Comercial"),
        ("VIVIENDA", "Vivienda"),
        # agrega aquí las reales cuando las confirmes
    ]

    GARANTIA_CHOICES = [
        ("PERSONAL", "Personal"),
        ("HIPOTECARIA", "Hipotecaria"),
        ("PRENDARIA", "Prendaria"),
        ("SOLIDARIA", "Solidaria"),
        # agrega aquí las reales
    ]

    CALIF_CHOICES = [
        ("A1","A1"), ("A2","A2"), ("A3","A3"),
        ("B1","B1"), ("B2","B2"),
        ("C1","C1"), ("C2","C2"),
        ("D","D"), ("E","E"),
    ]
    cliente = models.CharField(max_length=32, unique=True)
    oficina = models.CharField(max_length=32, blank=True, default="")  # si luego quieres choices, lo hacemos
    tipo_credito = models.CharField(max_length=64, blank=True, default="", choices=TIPO_CREDITO_CHOICES)
    garantia = models.CharField(max_length=64, blank=True, default="", choices=GARANTIA_CHOICES)
    sexo = models.CharField(max_length=8, blank=True, default="", choices=SEX_CHOICES)

    # calificación: la guardas pero NO la editas desde UI
    calificacion_riesgo = models.CharField(max_length=8, blank=True, default="", choices=CALIF_CHOICES)

    # riesgo_actual debería ser derivado; se mantiene pero no editable desde UI
    riesgo_actual = models.BooleanField(default=False)

    # ✅ Estado vigente por norma (tabla morosidad)
    categoria_norma = models.CharField(max_length=2, null=True, blank=True)  # A1,A2,A3,B1,B2,C1,C2,D,E
    nivel_norma = models.CharField(max_length=32, null=True, blank=True)     # "Riesgo Normal", etc.

    n_operaciones = models.IntegerField(null=True, blank=True)
    n_vigentes = models.IntegerField(null=True, blank=True)
    monto_total = models.FloatField(null=True, blank=True)
    saldo_total = models.FloatField(null=True, blank=True)
    plazo_prom = models.FloatField(null=True, blank=True)
    tasa_prom = models.FloatField(null=True, blank=True)
    patrimonio_tec = models.FloatField(null=True, blank=True)

    max_dias_mora = models.IntegerField(null=True, blank=True)
    antiguedad_max_dias = models.IntegerField(null=True, blank=True)
    dias_hasta_ultimo_venc = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    
    ml_proba_last = models.FloatField(null=True, blank=True)   # 0..1
    ml_pred_last = models.BooleanField(null=True, blank=True)  # True=alto, False=bajo
    ml_scored_at = models.DateTimeField(null=True, blank=True)
    ml_scored_by = models.CharField(max_length=150, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CreditOperation(models.Model):
    batch = models.ForeignKey(DataBatch, null=True, blank=True, on_delete=models.SET_NULL)

    cliente = models.CharField(max_length=32)
    oficina = models.CharField(max_length=32, blank=True, default="")
    estado = models.CharField(max_length=32, blank=True, default="")

    fecha_concesion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_corte_base = models.DateField(null=True, blank=True)

    monto_otorgado = models.FloatField(null=True, blank=True)
    saldo_total = models.FloatField(null=True, blank=True)
    tipo_credito = models.CharField(max_length=64, blank=True, default="")
    plazo = models.IntegerField(null=True, blank=True)
    tasa_interes = models.FloatField(null=True, blank=True)
    garantia = models.CharField(max_length=64, blank=True, default="")

    calificacion_riesgo = models.CharField(max_length=8, blank=True, default="")  # contraste/reglas
    dias_mora = models.IntegerField(null=True, blank=True)
    sexo = models.CharField(max_length=8, blank=True, default="")
    patrimonio_tec = models.FloatField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["cliente"]),
        ]

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile({self.user.username})"

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)

# datahub/models.py
from django.conf import settings
from django.db import models

class CustomerRiskHistory(models.Model):
    customer = models.ForeignKey(
        "datahub.CustomerAggregate",
        on_delete=models.CASCADE,
        related_name="risk_history",
    )

    # antes/después (formato DB: A1, A2, A3... sin guion)
    categoria_anterior = models.CharField(max_length=2, null=True, blank=True)
    categoria_nueva = models.CharField(max_length=2)

    nivel = models.CharField(max_length=32)
    dias_mora = models.IntegerField(default=0)
    tipo_credito = models.CharField(max_length=32, null=True, blank=True)

    # scoring
    proba_ml = models.FloatField(null=True, blank=True)          # 0..1
    proba_final = models.FloatField(null=True, blank=True)       # 0..1 (ajustada por norma)
    pred_ml = models.BooleanField(default=False)

    # auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


from django.db import models
from django.conf import settings

class CustomerAggregateHistory(models.Model):
    cliente = models.ForeignKey(
        "CustomerAggregate",
        on_delete=models.CASCADE,
        related_name="history"
    )

    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # "EDIT" (cambio de campos), "SCORE" (evaluación), etc.
    action = models.CharField(max_length=16, default="EDIT")

    # snapshot/diff
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    diff_json = models.JSONField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.cliente_id} {self.action} {self.changed_at}"
