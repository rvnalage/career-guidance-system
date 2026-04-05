from fastapi import APIRouter

from app.api.routes import auth, chat, dashboard, history, llm, market, modeling, profile_intake, psychometric, rag, recommendations, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(psychometric.router, prefix="/psychometric", tags=["psychometric"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(modeling.router, prefix="/modeling", tags=["modeling"])
api_router.include_router(profile_intake.router, prefix="/profile-intake", tags=["profile-intake"])
