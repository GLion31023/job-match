from fastapi import APIRouter
from app.api.api_v1.endpoints import users, login, utils, professionals, companies, ads

api_router = APIRouter()

api_router.include_router(users.router)
api_router.include_router(login.router)
api_router.include_router(utils.router)
api_router.include_router(professionals.router)
api_router.include_router(companies.router)
api_router.include_router(ads.router)
