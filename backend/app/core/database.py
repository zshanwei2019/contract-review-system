from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select
from typing import AsyncGenerator
import logging

from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_data()
    # 初始化默认角色/权限/超级管理员 (幂等: 已有数据时自动跳过)
    try:
        from app.core.init_data import init_default_data
        await init_default_data()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"默认数据初始化跳过: {e}")


async def _seed_data():
    """Insert seed data for seals and integration configs if tables are empty."""
    from app.models.signature import Seal
    from app.models.integration import IntegrationConfig

    async with async_session_factory() as session:
        # Seed seals
        result = await session.execute(select(Seal).limit(1))
        if result.scalars().first() is None:
            session.add_all([
                Seal(
                    name="公司公章",
                    seal_type="official",
                    image_url="/seals/official.png",
                    certificate_sn="CERT-SEAL-001",
                    is_active=True,
                ),
                Seal(
                    name="合同专用章",
                    seal_type="contract",
                    image_url="/seals/contract.png",
                    certificate_sn="CERT-SEAL-002",
                    is_active=True,
                ),
                Seal(
                    name="财务专用章",
                    seal_type="finance",
                    image_url="/seals/finance.png",
                    certificate_sn="CERT-SEAL-003",
                    is_active=True,
                ),
            ])
            logging.info("Seeded 3 seals")

        # Seed integration configs
        result = await session.execute(select(IntegrationConfig).limit(1))
        if result.scalars().first() is None:
            session.add_all([
                IntegrationConfig(
                    name="OA协同办公系统",
                    system_type="oa",
                    api_url="https://oa.example.com/api/v1",
                    auth_type="bearer",
                    sync_enabled=False,
                    sync_interval=300,
                    sync_direction="bidirectional",
                    is_active=True,
                ),
                IntegrationConfig(
                    name="ERP企业资源系统",
                    system_type="erp",
                    api_url="https://erp.example.com/api",
                    auth_type="api_key",
                    sync_enabled=False,
                    sync_interval=600,
                    sync_direction="inbound",
                    is_active=True,
                ),
            ])
            logging.info("Seeded 2 integration configs")

        await session.commit()
