from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional
from datetime import datetime
import hashlib
import json

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.signature import SignatureRequest, Seal, SignatureLog
from app.models.contract import Contract
from app.schemas.signature import (
    SealResponse, SealCreate,
    SignatureRequestResponse, SignatureRequestCreate,
)

router = APIRouter()


# ============ 印章管理 ============

@router.get("/seals", response_model=list[SealResponse])
async def list_seals(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Seal).order_by(desc(Seal.created_at))
    if active_only:
        query = query.where(Seal.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/seals", response_model=SealResponse)
async def create_seal(
    seal: SealCreate,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    db_seal = Seal(
        name=seal.name,
        seal_type=seal.seal_type,
        image_url=seal.image_url,
        certificate_sn=seal.certificate_sn,
        certificate_expiry=seal.certificate_expiry,
        owner_id=current_user.id,
    )
    db.add(db_seal)
    await db.flush()
    await db.refresh(db_seal)
    return db_seal


@router.put("/seals/{seal_id}/toggle")
async def toggle_seal(
    seal_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    seal = await db.get(Seal, seal_id)
    if not seal:
        raise HTTPException(404, "印章不存在")
    seal.is_active = not seal.is_active
    await db.flush()
    return {"id": seal_id, "is_active": seal.is_active}


@router.delete("/seals/{seal_id}")
async def delete_seal(
    seal_id: int,
    current_user: User = Depends(require_role("admin", "superadmin")),
    db: AsyncSession = Depends(get_db),
):
    seal = await db.get(Seal, seal_id)
    if not seal:
        raise HTTPException(404, "印章不存在")
    await db.delete(seal)
    return {"detail": "已删除"}


# ============ 签章请求 ============

@router.get("/requests", response_model=list[SignatureRequestResponse])
async def list_signature_requests(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    contract_id: Optional[int] = None,
    status: Optional[str] = None,
    signer_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SignatureRequest).order_by(desc(SignatureRequest.created_at))
    if contract_id:
        query = query.where(SignatureRequest.contract_id == contract_id)
    if status:
        query = query.where(SignatureRequest.status == status)
    if signer_name:
        query = query.where(SignatureRequest.signer_name.ilike(f"%{signer_name}%"))
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/requests/count")
async def count_signature_requests(
    contract_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(func.count(SignatureRequest.id))
    if contract_id:
        query = query.where(SignatureRequest.contract_id == contract_id)
    if status:
        query = query.where(SignatureRequest.status == status)
    result = await db.execute(query)
    return {"total": result.scalar()}


@router.post("/requests", response_model=SignatureRequestResponse)
async def create_signature_request(
    req: SignatureRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证合同存在
    contract = await db.get(Contract, req.contract_id)
    if not contract:
        raise HTTPException(404, "合同不存在")

    # 获取印章图片
    seal_image_url = None
    if req.seal_id:
        seal = await db.get(Seal, req.seal_id)
        if seal:
            seal_image_url = seal.image_url

    db_req = SignatureRequest(
        contract_id=req.contract_id,
        signer_name=req.signer_name,
        signer_email=req.signer_email,
        signer_phone=req.signer_phone,
        signer_id_number=req.signer_id_number,
        signature_type=req.signature_type,
        position=req.position,
        seal_image_url=seal_image_url,
        status="pending",
        expires_at=req.expires_at,
        remark=req.remark,
        created_by=current_user.id,
    )
    db.add(db_req)
    await db.flush()

    # 记录日志
    db.add(SignatureLog(
        signature_request_id=db_req.id,
        action="create",
        operator=current_user.username,
        detail=f"创建签章请求: {req.signer_name}",
    ))
    await db.refresh(db_req)
    return db_req


@router.post("/requests/{req_id}/sign")
async def sign_request(
    req_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """模拟签署（生成哈希 + 证书序列号）"""
    req = await db.get(SignatureRequest, req_id)
    if not req:
        raise HTTPException(404, "签章请求不存在")
    if req.status != "pending":
        raise HTTPException(400, f"当前状态({req.status})不可签署")

    # 模拟数字签名
    raw = f"{req.id}:{req.contract_id}:{req.signer_name}:{datetime.utcnow().isoformat()}"
    req.hash_value = hashlib.sha256(raw.encode()).hexdigest()
    req.certificate_sn = f"CERT-{req.id:06d}-{datetime.utcnow().strftime('%Y%m%d')}"
    req.certificate_issuer = "贵州西工CA中心"
    req.status = "signed"
    req.signed_at = datetime.utcnow()

    db.add(SignatureLog(
        signature_request_id=req.id,
        action="sign",
        operator=current_user.username,
        detail=f"签署完成，证书SN: {req.certificate_sn}",
    ))
    await db.flush()
    return {
        "detail": "签署成功",
        "certificate_sn": req.certificate_sn,
        "hash_value": req.hash_value,
        "signed_at": req.signed_at.isoformat(),
    }


@router.post("/requests/{req_id}/reject")
async def reject_request(
    req_id: int,
    reason: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    req = await db.get(SignatureRequest, req_id)
    if not req:
        raise HTTPException(404, "签章请求不存在")
    if req.status != "pending":
        raise HTTPException(400, f"当前状态({req.status})不可驳回")
    req.status = "rejected"
    db.add(SignatureLog(
        signature_request_id=req.id,
        action="reject",
        operator=current_user.username,
        detail=f"驳回: {reason}",
    ))
    await db.flush()
    return {"detail": "已驳回"}


@router.post("/requests/{req_id}/revoke")
async def revoke_request(
    req_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    req = await db.get(SignatureRequest, req_id)
    if not req:
        raise HTTPException(404, "签章请求不存在")
    req.status = "revoked"
    db.add(SignatureLog(
        signature_request_id=req.id,
        action="revoke",
        operator=current_user.username,
        detail="撤销签章",
    ))
    await db.flush()
    return {"detail": "已撤销"}


@router.get("/requests/{req_id}/verify")
async def verify_signature(
    req_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """验证签章"""
    req = await db.get(SignatureRequest, req_id)
    if not req:
        raise HTTPException(404, "签章请求不存在")
    if req.status != "signed":
        raise HTTPException(400, "未签署，无法验证")

    return {
        "valid": True,
        "certificate_sn": req.certificate_sn,
        "certificate_issuer": req.certificate_issuer,
        "hash_value": req.hash_value,
        "signed_at": req.signed_at.isoformat(),
        "signer_name": req.signer_name,
        "contract_id": req.contract_id,
    }


@router.get("/requests/{req_id}/logs")
async def signature_logs(
    req_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SignatureLog).where(SignatureLog.signature_request_id == req_id).order_by(desc(SignatureLog.created_at))
    result = await db.execute(query)
    return result.scalars().all()
