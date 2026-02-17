from django import forms
from .models import DataBatch, CustomerAggregate

TIPOS_CREDITO_PERMITIDOS = [
    ("CONSUMO", "Consumo"),
    ("MICROCREDITO", "Microcrédito"),
    ("VIVIENDA", "Vivienda"),
]

class UploadDataForm(forms.ModelForm):
    class Meta:
        model = DataBatch
        fields = ["load_mode", "file"]

class CustomerAggregateForm(forms.ModelForm):
    class Meta:
        model = CustomerAggregate
        exclude = ["batch", "created_at", "updated_at", "riesgo_actual","ml_proba_last", "ml_pred_last", "ml_scored_at", "ml_scored_by"]  # y lo que estés excluyendo

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # cliente siempre disabled
        if "cliente" in self.fields:
            self.fields["cliente"].disabled = True

        # calificacion_riesgo: solo si existe en el form
        if "calificacion_riesgo" in self.fields:
            self.fields["calificacion_riesgo"].disabled = True

        # tipo_credito: solo si existe en el form
        if "tipo_credito" in self.fields:
            self.fields["tipo_credito"].choices = TIPOS_CREDITO_PERMITIDOS  # limita los valores permitidos

        # --- Oficina solo lectura ---
        if "oficina" in self.fields:
            self.fields["oficina"].disabled = True

    def clean_oficina(self):
        if self.instance and self.instance.pk:
            return self.instance.oficina
        return self.cleaned_data.get("oficina")