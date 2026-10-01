from fastapi import APIRouter

from app.api.v1 import dashboard, drivers, expenses, journeys, reports, vehicles

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(dashboard.router)
api_router.include_router(vehicles.router)
api_router.include_router(drivers.router)
api_router.include_router(journeys.router)
api_router.include_router(expenses.router)
api_router.include_router(expenses.categories_router)
api_router.include_router(reports.router)
