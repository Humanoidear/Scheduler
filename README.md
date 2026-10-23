# Scheduler

Aplicación web para gestión de eventos con inscripciones por fecha.

## Tecnologías

- Flask + Flask-Login + Flask-WTF + SQLAlchemy
- PostgreSQL
- Tailwind CSS con diseño Material 3 Expressive
- Docker + Docker Compose
- Gunicorn

## Ejecutar en producción

```bash
cp .env.example .env
# Edita .env con SECRET_KEY, ADMIN_USERNAME y ADMIN_PASSWORD seguros
docker compose up --build -d
```

La app estará disponible en `http://localhost:8080`.

## Credenciales iniciales

El administrador se crea automáticamente desde las variables de entorno `ADMIN_USERNAME` y `ADMIN_PASSWORD`.

## Funcionalidades

- Admin: crea eventos con múltiples fechas, define cupos y decide si los asistentes se muestran públicamente o si un usuario puede inscribirse en varias fechas del mismo evento.
- Admin: crea usuarios con contraseña inicial común.
- Admin: descarga un PDF con el listado de inscritos por fecha para cada evento.
- Admin: exporta e importa eventos en formato JSON desde el panel.
- Usuario: inicia sesión, cambia la contraseña obligatoriamente en el primer ingreso, se inscribe en fechas desde un calendario y consulta sus inscripciones en "Mis eventos".

## Poblar la base de datos (desarrollo)

Para generar datos de prueba (usuarios, eventos y turnos):

```bash
docker compose exec web python seed.py
```

Usuarios de prueba: PIN `1234`. Admin: según variables de entorno.
