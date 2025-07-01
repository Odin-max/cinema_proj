from fastapi import FastAPI

from .services.auth import router as auth_router
from .db.session import init_db
from .core.config import settings

from .routes.movies import router as movies_router
from .routes.genres.genres import router as admin_genres_router
from .routes.stars.stars import router as admin_stars_router
from .routes.directors.directors import router as admin_directors_router
from .routes.certifications.certifications import router as admin_certifications_router
from .routes.admin.admin_movies import router as admin_movies_router
from .routes.cart.carts import router as cart_router
from .routes.orders.orders import router as order_router


app = FastAPI(title="Cinema Auth")

@app.on_event("startup")
async def on_startup():
    await init_db()


app.include_router(auth_router, prefix="/auth", tags=["auth"])


app.include_router(movies_router)

app.include_router(admin_genres_router)
app.include_router(admin_stars_router)
app.include_router(admin_directors_router)
app.include_router(admin_certifications_router)
app.include_router(admin_movies_router)
app.include_router(cart_router)
app.include_router(order_router)