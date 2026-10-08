from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    chat,
    conversations,
    dashboard,
    documents,
    exams,
    interviews,
    learning,
    system,
)

api_router = APIRouter()

api_router.include_router(system.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(exams.router, prefix="/exams", tags=["exams"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


