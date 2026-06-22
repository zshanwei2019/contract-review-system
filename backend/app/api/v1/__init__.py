from fastapi import APIRouter

from app.api.v1 import auth, users, contracts, reviews, workflows, risks, notifications, dashboard, agent, advanced_review, clause_library, contract_templates, audit, signature, integration

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["合同管理"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["审查管理"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["工作流"])
api_router.include_router(risks.router, prefix="/risks", tags=["风险管理"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知管理"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["仪表盘"])
api_router.include_router(agent.router, prefix="/agent", tags=["AI智能体"])
api_router.include_router(advanced_review.router, tags=["AI高级审查"])
api_router.include_router(clause_library.router, prefix="/clause-library", tags=["条款库"])
api_router.include_router(audit.router, prefix="/audit", tags=["审计日志"])
api_router.include_router(signature.router, prefix="/signature", tags=["电子签章"])
api_router.include_router(integration.router, prefix="/integration", tags=["外部集成"])
