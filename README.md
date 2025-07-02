# Cinema API

This is a FastAPI-based microservice for a cinema application, featuring user registration/authentication, movie listings, genres, stars, directors, certifications, shopping cart, and order processing with Stripe payments. Celery is used for background tasks.

---

## 📋 Prerequisites

- Docker & Docker Compose
- Python 3.13 (if running without Docker)
- Poetry (for dependency management)

---

## ⚙️ Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Odin-max/cinema_proj.git
   cd cinema_proj
   ```

2. **Copy `.env.sample` to `.env` and fill in your secrets**
   ```bash
   cp .env.sample .env
   # Edit .env with your values
   ```

3. **(Optional) Install dependencies locally**
   ```bash
   poetry install
   ```

4. **To see all endpoints use:**
   ```bash
   127.0.0.1:8000/docs
   ```

---


## 🚀 Running with Docker Compose

The project comes with a `docker-compose.yml` that spins up the following services:

- **PostgreSQL** (DB)
- **Redis** (Celery broker & result backend)
- **MailHog** (SMTP testing)
- **FastAPI** web server
- **Celery worker**
- **Celery beat**

```bash
# Build and start all services
docker-compose up --build -d

# Watch logs for the web service
docker-compose logs -f web
```

### Database Migrations

```bash
# In a running container or locally (with PYTHONPATH=src):
poetry run alembic upgrade head
```

---

## 🧪 Running Tests

```bash
poetry run pytest -q
```

---

## 📦 Starting Celery Services

```bash
# Celery worker
docker-compose exec celery_worker celery -A app.celery_app worker -E --pool=solo -Q celery,maintenance

# Celery beat
docker-compose exec celery_beat celery -A app.celery_app beat --loglevel=info
```

---

## 🛠️ Environment Variables

| Variable                | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| POSTGRES_USER           | PostgreSQL username                                      |
| POSTGRES_PASSWORD       | PostgreSQL password                                      |
| POSTGRES_DB             | PostgreSQL database name                                 |
| POSTGRES_HOST           | DB host (e.g. `postgres` in Docker network)             |
| POSTGRES_DB_PORT        | DB port inside container (5432)                          |
| DATABASE_URL            | SQLAlchemy database URL (asyncpg)                        |
| SECRET_KEY_ACCESS       | JWT secret for access tokens                             |
| SECRET_KEY_REFRESH      | JWT secret for refresh tokens                            |
| JWT_SIGNING_ALGORITHM   | JWT algorithm (e.g. `HS256`)                             |
| EMAIL_HOST              | SMTP host for sending emails (MailHog: `mailhog`)        |
| EMAIL_PORT              | SMTP port (MailHog: 1025)                                |
| EMAIL_HOST_USER         | SMTP username                                            |
| EMAIL_HOST_PASSWORD     | SMTP password                                            |
| EMAIL_USE_TLS           | `True`/`False`                                          |
| CELERY_BROKER_URL       | Redis broker URL (e.g. `redis://redis:6379/0`)           |
| CELERY_RESULT_BACKEND   | Redis backend URL (e.g. `redis://redis:6379/1`)          |
| BACKEND_URL             | Base URL of this service (for email links, etc.)         |
| DEFAULT_GROUP_ID        | Default user group ID                                    |
| STRIPE_PUBLISHABLE_KEY  | Stripe publishable API key                               |
| STRIPE_SECRET_KEY       | Stripe secret API key                                    |
| STRIPE_WEBHOOK_SECRET   | Stripe webhook secret key                                |

---

## 📡 API Endpoints

### Authentication

| Method | Path                 | Description               |
| ------ | -------------------- | ------------------------- |
| POST   | `/auth/register`     | Register new user         |
| POST   | `/auth/login`        | Obtain JWT tokens         |
| POST   | `/auth/refresh`      | Refresh access token      |

### Movies

| Method | Path                      | Description                              |
| ------ | ------------------------- | ---------------------------------------- |
| GET    | `/movies`                 | List all movies                          |
| GET    | `/movies/{movie_id}`      | Get movie details                       |
| GET    | `/movies/search`          | Search movies by title, genre, etc.     |

### Genres

| Method | Path                         | Description                          |
| ------ | ---------------------------- | ------------------------------------ |
| GET    | `/genres`                    | List all genres                      |
| GET    | `/genres/{genre_id}/movies`  | Get movies in a genre               |

### Stars & Directors & Certifications

| Entity           | Method | Path                           | Description                         |
| ---------------- | ------ | ------------------------------ | ----------------------------------- |
| Stars            | GET    | `/stars`                       | List all stars                      |
|                  | GET    | `/stars/{star_id}/movies`      | Movies by a star                    |
| Directors        | GET    | `/directors`                   | List all directors                  |
|                  | GET    | `/directors/{dir_id}/movies`   | Movies by a director                |
| Certifications   | GET    | `/certifications`              | List all certifications             |
|                  | GET    | `/certifications/{cert_id}`    | Details for a certification         |

### Cart

| Method | Path                  | Description              |
| ------ | --------------------- | ------------------------ |
| GET    | `/cart`               | Get current user’s cart  |
| POST   | `/cart/add`           | Add item to cart         |
| POST   | `/cart/remove`        | Remove item from cart    |

### Orders

| Method | Path                  | Description                      |
| ------ | --------------------- | -------------------------------- |
| GET    | `/orders`             | List user orders                 |
| POST   | `/orders`             | Create new order (checkout)      |
| GET    | `/orders/{order_id}`  | Get specific order details       |

### Admin (requires admin role)

| Method | Path                        | Description                      |
| ------ | --------------------------- | -------------------------------- |
| GET    | `/admin/movies`             | List & manage movies            |
| POST   | `/admin/movies`             | Create a new movie               |
| PATCH  | `/admin/movies/{movie_id}`  | Update movie details             |
| DELETE | `/admin/movies/{movie_id}`  | Delete a movie                   |

---
