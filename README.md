# Sistema de Evaluación Crediticia (Django)

Aplicación web para cargar datos crediticios, visualizar clientes/operaciones y calcular riesgo de crédito con un enfoque híbrido:

- Reglas de morosidad (tabla normativa por tipo de crédito y días de mora).
- Modelo de Machine Learning (probabilidad de riesgo alto).

## Qué hace el sistema

El proyecto implementa los siguientes módulos:

- `accounts`: login/logout, recuperación de contraseña y middleware para forzar cambio de clave si el perfil lo requiere.
- `datahub`: carga de archivos (`CSV`, `XLS`, `XLSX`), trazabilidad de batches, catálogo de clientes agregados y operaciones.
- `scoring`: inferencia con modelo `.joblib` y reglas para decisión final.

Flujo funcional principal:

1. Subir archivo en modo `CUSTOMER_AGG` o `OPERATION`.
2. Importar y filtrar columnas permitidas (whitelist).
3. Consultar clientes y ejecutar scoring por cliente.
4. Guardar último resultado ML (`ml_proba_last`, `ml_pred_last`, `ml_scored_at`, `ml_scored_by`).

## Stack tecnológico

- Python 3.10.9 (entorno virtual `.venv`)
- Django 5.2.x
- PostgreSQL (configurado como motor principal en `config/settings.py`)
- pandas / numpy
- scikit-learn / joblib
- openpyxl (lectura `.xlsx`)
- xlrd (lectura `.xls`, recomendado)
- Bootstrap 5 (CDN)

## Estructura relevante

- `config/`: settings y rutas globales.
- `accounts/`: autenticación.
- `datahub/`: modelos de lotes, clientes y operaciones; importador; comando de gestión.
- `scoring/`: reglas y servicio de scoring ML.
- `data/`: datasets y artefactos de modelo.
- `templates/`: vistas HTML.

## Requisitos previos

En Windows (PowerShell):

```powershell
python --version
```

Instalar dependencias mínimas:

```powershell
pip install -r requirements.txt
```

## Ejecución del proyecto

Desde la raíz `ML_cooperativa`:

1. Crear y activar entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Ejecutar migraciones:

```powershell
python manage.py migrate
```

4. Crear usuario administrador:

```powershell
python manage.py createsuperuser
```

5. Levantar servidor:

```powershell
python manage.py runserver
```

6. Abrir en navegador:

- App: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Uso básico en la app

1. Ingresar con usuario creado.
2. Ir a `Cargar datos`.
3. Elegir modo `CUSTOMER_AGG` (agregado por cliente) o `OPERATION` (detalle por operación).
4. Subir archivo.
5. Revisar `Batches` para estado de carga.
6. Ir a `Clientes` para ver detalle y usar `Evaluar con modelo`.

## Formato esperado de archivos

El importador normaliza nombres de columna a minúsculas y aplica whitelist.

### Modo `CUSTOMER_AGG`

Columnas requeridas:

- `cliente`
- `max_dias_mora`

Columnas soportadas:

- `cliente`, `oficina`, `tipo_credito`, `garantia`, `sexo`, `calificacion_riesgo`
- `n_operaciones`, `n_vigentes`, `monto_total`, `saldo_total`, `plazo_prom`, `tasa_prom`
- `patrimonio_tec`, `max_dias_mora`, `antiguedad_max_dias`, `dias_hasta_ultimo_venc`

### Modo `OPERATION`

Columnas requeridas:

- `cliente`

Columnas soportadas:

- `cliente`, `oficina`, `estado`
- `fecha_concesion`, `fecha_vencimiento`, `fecha_corte_base`
- `monto_otorgado`, `saldo_total`, `tipo_credito`, `plazo`, `tasa_interes`, `garantia`
- `calificacion_riesgo`, `dias_mora`, `sexo`, `patrimonio_tec`

## Scoring y reglas de riesgo

El endpoint de scoring combina:

- Probabilidad ML (`pipeline.predict_proba`).
- Clasificación normativa por morosidad (`classify_morosidad`).
- Ajuste por piso de probabilidad (`adjust_probability_by_category`).

Decisión final:

- `D/E` -> `RECHAZAR`
- `C-1/C-2` -> `REVISIÓN`
- `A/B` -> según umbral de probabilidad

## Comandos útiles

Recalcular `riesgo_actual` para todos los clientes con la tabla normativa:

```powershell
python manage.py recalcular_riesgo
```

Verificar configuración Django:

```powershell
python manage.py check
```

## Entrenamiento del modelo (opcional)

Script:

- `data/Trainer.py`

Entrada esperada:

- `data/BDD_COACTULCAN.xlsx`

Salida del script:

- `data/models/credit_risk_customer_model.joblib`

Nota importante: la app carga por defecto el modelo desde:

- `data/credit_risk_customer_model.joblib` (definido en `config/settings.py` como `ML_MODEL_PATH`)

Si reentrenas, copia el artefacto o ajusta `ML_MODEL_PATH`.

## Estado actual y notas

- Entorno virtual validado: `.venv` con Python `3.10.9`.
- Dependencias del proyecto definidas en `requirements.txt`.
- Conexión a PostgreSQL activa en `config/settings.py` (`ENGINE = django.db.backends.postgresql`).
- La base PostgreSQL actual está vacía (migraciones aún no aplicadas en ese motor; `showmigrations` aparece en estado pendiente).
- El proyecto incluye un CSV de ejemplo en `data/dataset_clientes_agregado.csv`.
- El flujo principal de login/carga/scoring está operativo.
- Existen rutas de registro/cambio de contraseña en `accounts`, pero revisa plantillas si habilitarás ese flujo completo en producción.

## Seguridad y despliegue

Configuración actual es de desarrollo:

- `DEBUG=True`
- `ALLOWED_HOSTS=[]`
- `SECRET_KEY` embebida en código

Antes de producción: mover secretos a variables de entorno, configurar hosts, base de datos robusta y hardening de Django.
