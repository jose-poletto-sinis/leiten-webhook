# leiten-webhook

Webhook receiver que escucha eventos de **Pull Request** en GitHub y envía un email de notificación al autor del PR antes de que se haga el merge.

## Setup rápido

```bash
# 1. Clonar e instalar
git clone https://github.com/grupoLeiten/leiten-webhook.git
cd leiten-webhook
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales SMTP y webhook secret

# 3. Correr
python app.py
```

## Variables de entorno

| Variable | Descripción |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | Secret compartido con GitHub para validar firmas |
| `SMTP_HOST` | Host del servidor SMTP (default: `smtp.gmail.com`) |
| `SMTP_PORT` | Puerto SMTP (default: `587`) |
| `SMTP_USER` | Usuario SMTP (tu email) |
| `SMTP_PASSWORD` | Contraseña o App Password de SMTP |
| `EMAIL_FROM` | Dirección "From" del email |

## Configurar el webhook en GitHub

1. Ir al repo donde querés las notificaciones → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `https://tu-servidor.com/webhook`
3. **Content type**: `application/json`
4. **Secret**: el mismo valor que `GITHUB_WEBHOOK_SECRET`
5. **Events**: seleccionar solo **Pull requests**
6. Guardar

## Producción

```bash
gunicorn app:app --bind 0.0.0.0:5000
```
