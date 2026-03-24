# Sistema de Evaluación Crediticia (Django)

Aplicación web para cargar datos crediticios, visualizar clientes/operaciones y calcular riesgo de crédito con un enfoque híbrido:

- Reglas de morosidad (tabla normativa por tipo de crédito y días de mora).
- Modelo de Machine Learning (probabilidad de riesgo alto).

## Qué hace el sistema

El proyecto implementa los siguientes módulos:

- `accounts`: login/logout, registro, cambio de contraseña, recuperación de contraseña por correo y middleware para forzar cambio de clave si el perfil lo requiere.
- `datahub`: carga de archivos (`CSV`, `XLS`, `XLSX`), trazabilidad de batches, catálogo de clientes agregados y operaciones.
- `scoring`: inferencia con modelo `.joblib` y reglas para decisión final.

Flujo funcional principal:

1. Subir archivo en modo `CUSTOMER_AGG` o `OPERATION`.
2. Importar y filtrar columnas permitidas (whitelist).
3. Consultar clientes y ejecutar scoring por cliente.
4. Guardar último resultado ML (`ml_proba_last`, `ml_pred_last`, `ml_scored_at`, `ml_scored_by`).

## Stack tecnológico

| Paquete | Versión | Uso |
|---|---|---|
| Python | 3.10.9 | Entorno virtual `.venv` |
| Django | 5.2.11 | Framework principal |
| PostgreSQL | — | Motor de base de datos |
| psycopg[binary] | 3.3.2 | Driver PostgreSQL |
| pandas | 2.3.3 | Procesamiento de datos |
| numpy | 2.2.6 | Cómputo numérico |
| scikit-learn | 1.7.2 | Modelo ML |
| joblib | 1.5.3 | Serialización de modelo |
| openpyxl | 3.1.5 | Lectura `.xlsx` |
| xlrd | 2.0.1 | Lectura `.xls` |
| reportlab | 4.4.4 | Generación de PDFs |
| matplotlib | 3.10.8 | Gráficos |
| python-dotenv | 1.2.2 | Variables de entorno desde `.env` |
| Bootstrap 5 | CDN | Estilos frontend |

## Estructura relevante

```
ML_cooperativa/
├── .env                  ← Variables de entorno (NO subir a Git)
├── config/               ← settings, urls, wsgi/asgi
├── accounts/             ← autenticación, password reset, middleware
├── datahub/              ← modelos de lotes, clientes, operaciones e importador
├── scoring/              ← reglas y servicio de scoring ML
├── data/                 ← datasets y artefactos del modelo
├── templates/            ← vistas HTML (base, accounts, datahub, scoring)
├── static/               ← CSS/JS estáticos
├── requirements.txt
└── manage.py
```

## Requisitos previos

En Windows (PowerShell):

```powershell
python --version   # debe ser 3.10.x
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

3. Crear el archivo `.env` (ver sección [Configuración de variables de entorno](#configuración-de-variables-de-entorno)):

```powershell
# Edita .env con tus valores reales antes de continuar
```

4. Ejecutar migraciones:

```powershell
python manage.py migrate
```

5. Crear usuario administrador:

```powershell
python manage.py createsuperuser
```

6. Levantar servidor:

```powershell
python manage.py runserver
```

7. Abrir en navegador:

- App: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Configuración de variables de entorno

El proyecto usa `python-dotenv` para cargar configuración desde un archivo `.env` en la raíz. Este archivo **no se incluye en el repositorio** (está en `.gitignore`).

Crea el archivo `ML_cooperativa/.env` con el siguiente contenido:

```env
# ── Email (Mailtrap Sandbox para pruebas) ──────────────────────────────────
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_PORT=587
EMAIL_HOST_USER=<tu_usuario_mailtrap>
EMAIL_HOST_PASSWORD=<tu_password_mailtrap>
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=no-reply@cooperativa.local
```

> **Dónde obtener las credenciales de Mailtrap:**
> 1. Inicia sesión en [mailtrap.io](https://mailtrap.io)
> 2. Ve a **Email Testing → Inboxes**
> 3. Haz clic en tu inbox → pestaña **SMTP Settings**
> 4. Selecciona **Django** en el dropdown de integraciones
> 5. Copia `USERNAME` y `PASSWORD`

### Alternativa sin SMTP (solo terminal)

Para desarrollo sin correo real, usa el backend de consola (el enlace se imprime en la terminal del `runserver`):

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

## Uso básico en la app

1. Ingresar con usuario creado.
2. Ir a `Cargar datos`.
3. Elegir modo `CUSTOMER_AGG` (agregado por cliente) o `OPERATION` (detalle por operación).
4. Subir archivo.
5. Revisar `Batches` para estado de carga.
6. Ir a `Clientes` para ver detalle y usar `Evaluar con modelo`.

## Flujo de autenticación y contraseñas

El módulo `accounts` cubre el ciclo completo de credenciales:

| URL | Descripción |
|---|---|
| `/accounts/login/` | Inicio de sesión |
| `/accounts/logout/` | Cierre de sesión |
| `/accounts/password-change/` | Cambio de contraseña (usuario autenticado) |
| `/accounts/password-reset/` | Solicitar recuperación por correo |
| `/accounts/password-reset/done/` | Confirmación de envío |
| `/accounts/reset/<uidb64>/<token>/` | Establecer nueva contraseña |
| `/accounts/reset/done/` | Confirmación de restablecimiento |

**Middleware de cambio forzado:** si un usuario tiene `must_change_password=True` en su `UserProfile` y entra con la contraseña genérica (`123456789`), es redirigido automáticamente a `password-change` antes de poder acceder.

### Verificar el flujo de recuperación

```powershell
python manage.py shell -c "from django.core.mail import send_mail; send_mail('Test Mailtrap', 'OK', 'no-reply@cooperativa.local', ['tu@email.com']); print('OK')"
```

Si usas Mailtrap Sandbox, el correo aparece en tu inbox de pruebas. Si usas `console.EmailBackend`, se imprime en la terminal.

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

- `D/E` → `RECHAZAR`
- `C-1/C-2` → `REVISIÓN`
- `A/B` → según umbral de probabilidad

## Comandos útiles

Recalcular `riesgo_actual` para todos los clientes con la tabla normativa:

```powershell
python manage.py recalcular_riesgo
```

Verificar configuración Django:

```powershell
python manage.py check
```

Exportar datos en UTF-8:

```powershell
python manage.py dumpdata --exclude contenttypes --exclude auth.permission --exclude admin.logentry --output data_utf8.json
```

Cargar fixture en PostgreSQL:

```powershell
python manage.py loaddata data_utf8.json
```

Si el archivo fue guardado accidentalmente en `cp1252`, convertirlo antes de `loaddata`:

```powershell
python -c "from pathlib import Path; p=Path('data_utf8.json'); p.write_text(p.read_text(encoding='cp1252'), encoding='utf-8')"
```

## Entrenamiento del modelo (opcional)

Script: `data/Trainer.py`

Entrada: `data/BDD_COACTULCAN.xlsx`

Salida: `data/models/credit_risk_customer_model.joblib`

> La app carga por defecto el modelo desde `data/credit_risk_customer_model.joblib` (definido en `config/settings.py` como `ML_MODEL_PATH`). Si reentrenas, copia el artefacto o ajusta esa variable.

## Estado actual

- Entorno virtual: `.venv` con Python `3.10.9`.
- Motor de base de datos: PostgreSQL (`cooperativa_db` en `127.0.0.1:5432`).
- Migración a PostgreSQL completada: `users=1`, `batches=1`, `customers=1691`, `operations=0`.
- Flujo principal login / carga / scoring operativo.
- Sistema de recuperación de contraseña por correo configurado y validado con Mailtrap Sandbox.
- Variables de entorno gestionadas con `python-dotenv` (archivo `.env` excluido del repositorio).

## Seguridad y despliegue

Configuración actual es de **desarrollo**:

- `DEBUG=True`
- `ALLOWED_HOSTS=[]`
- `SECRET_KEY` embebida en código

Antes de producción:

- Mover `SECRET_KEY` y credenciales de BD/email a variables de entorno.
- Configurar `ALLOWED_HOSTS` y `DEBUG=False`.
- Usar un servidor SMTP real con dominio verificado (Mailtrap Email API o similar).
- Aplicar hardening de Django (`SECURE_*`, HTTPS, etc.).
