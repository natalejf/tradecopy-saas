# 🚀 TradeCopy SaaS — Guía de Deploy en la Nube

## Opción 1: Railway (RECOMENDADA — más fácil, ~$5/mes)

### Pasos:
1. Crear cuenta en https://railway.app
2. Instalar Railway CLI:
   ```bash
   npm install -g @railway/cli
   railway login
   ```
3. Desde la carpeta del proyecto:
   ```bash
   cd tradecopy-saas
   railway init
   railway up
   ```
4. Configurar variables de entorno en Railway dashboard:
   ```
   JWT_SECRET=una-cadena-aleatoria-larga-aqui
   ADMIN_KEY=tu-clave-admin-secreta
   DATABASE_URL=/data/tradecopy.db
   ```
5. Railway te da una URL tipo: `https://tradecopy-production.up.railway.app`

---

## Opción 2: Render (gratis limitado, $7/mes sin límite)

1. Crear cuenta en https://render.com
2. New → Web Service → conectar tu repo de GitHub
3. Settings:
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables: igual que Railway arriba
5. Para la base de datos usar: Render Disk ($1/mes) o migrar a PostgreSQL

---

## Opción 3: DigitalOcean Droplet (~$6/mes, más control)

### Setup inicial:
```bash
# En tu PC local - crear droplet Ubuntu 22.04
# Conectarse por SSH:
ssh root@TU-IP

# Instalar Docker
curl -fsSL https://get.docker.com | sh
apt install docker-compose -y

# Clonar/subir el proyecto
mkdir /opt/tradecopy && cd /opt/tradecopy
# Subir archivos via scp o git clone

# Editar variables en docker-compose.yml
nano docker-compose.yml
# Cambiar JWT_SECRET y ADMIN_KEY

# Lanzar
docker-compose up -d

# Ver logs
docker-compose logs -f
```

### Dominio + SSL (nginx + certbot):
```bash
apt install nginx certbot python3-certbot-nginx -y

# Crear config nginx
cat > /etc/nginx/sites-available/tradecopy << 'NGINX'
server {
    server_name tudominio.com www.tudominio.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX

ln -s /etc/nginx/sites-available/tradecopy /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# SSL gratuito con Let's Encrypt
certbot --nginx -d tudominio.com -d www.tudominio.com
```

---

## Migrar a PostgreSQL (producción seria)

Reemplazar SQLite por PostgreSQL para escalar:

```bash
# Instalar psycopg2
pip install psycopg2-binary

# En docker-compose.yml agregar:
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: tradecopy
      POSTGRES_USER: tc
      POSTGRES_PASSWORD: secret123
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    environment:
      - DATABASE_URL=postgresql://tc:secret123@db:5432/tradecopy
```

Modificar `core/database.py` para usar psycopg2 en lugar de sqlite3.
Railway y Render ofrecen PostgreSQL gratis/pago integrado.

---

## Configurar el EA en MT5

Una vez que el servidor esté online:

1. Descargar `TradeCopy_Master.mq5` y `TradeCopy_Follower.mq5`
2. Copiar a: `MetaTrader5/MQL5/Experts/`
3. Compilar en MetaEditor (F5)
4. En MT5: **Tools → Options → Expert Advisors**
   - ✅ Allow automated trading
   - ✅ Allow DLL imports
   - Agregar tu dominio en "Allowed URLs":
     `https://tudominio.com`
5. Arrastrar el EA al gráfico
6. Configurar:
   - `ServerURL`: `https://tudominio.com`
   - `EAToken`: el token que aparece en el dashboard

---

## Checklist de lanzamiento

- [ ] Servidor corriendo y accesible por HTTPS
- [ ] Dominio configurado con SSL
- [ ] Variables de entorno seguras (JWT_SECRET largo y aleatorio)
- [ ] Base de datos con persistencia (volumen Docker o PostgreSQL)
- [ ] Master EA instalado y enviando heartbeat (ver Dashboard)
- [ ] Follower EAs instalados y polling
- [ ] Copy group configurado con master → followers
- [ ] Primer trade copiado exitosamente ✅

---

## Monetización con Stripe

Para cobrar suscripciones:
1. Crear cuenta en https://stripe.com
2. Instalar: `pip install stripe`
3. Agregar webhook en `routers/subscriptions.py`:
```python
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    # Verificar firma de Stripe
    # Al completar pago: db.update_user_plan(user_id, 'pro', expires_at)
    pass
```
4. Usar Stripe Checkout o Payment Links para cada plan

