"""Initialize database with default data"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import get_password_hash
from app.models.user import User, Role, Permission, UserRole, RolePermission


# Default roles
DEFAULT_ROLES = [
    {"name": "超级管理员", "code": "superadmin", "description": "系统超级管理员，拥有所有权限"},
    {"name": "系统管理员", "code": "admin", "description": "系统管理员，管理用户和配置"},
    {"name": "法务主管", "code": "legal_manager", "description": "法务部门主管，负责任务分配和终审"},
    {"name": "法务专员", "code": "legal_specialist", "description": "法务专员，执行合同审查"},
    {"name": "业务部门负责人", "code": "business_manager", "description": "业务部门负责人，提交和查看合同"},
    {"name": "业务人员", "code": "business_staff", "description": "业务人员，提交合同"},
    {"name": "管理层", "code": "executive", "description": "公司管理层，查看报表"},
]

# Default permissions
DEFAULT_PERMISSIONS = [
    # User management
    {"name": "用户列表", "code": "user:list", "type": "button", "path": "/users"},
    {"name": "创建用户", "code": "user:create", "type": "button", "path": "/users"},
    {"name": "编辑用户", "code": "user:update", "type": "button", "path": "/users"},
    {"name": "删除用户", "code": "user:delete", "type": "button", "path": "/users"},
    
    # Contract management
    {"name": "合同列表", "code": "contract:list", "type": "button", "path": "/contracts"},
    {"name": "创建合同", "code": "contract:create", "type": "button", "path": "/contracts"},
    {"name": "编辑合同", "code": "contract:update", "type": "button", "path": "/contracts"},
    {"name": "删除合同", "code": "contract:delete", "type": "button", "path": "/contracts"},
    {"name": "提交合同", "code": "contract:submit", "type": "button", "path": "/contracts"},
    {"name": "审批合同", "code": "contract:approve", "type": "button", "path": "/contracts"},
    
    # Review management
    {"name": "审查列表", "code": "review:list", "type": "button", "path": "/reviews"},
    {"name": "分配审查", "code": "review:assign", "type": "button", "path": "/reviews"},
    {"name": "执行审查", "code": "review:execute", "type": "button", "path": "/reviews"},
    {"name": "审查意见", "code": "review:opinion", "type": "button", "path": "/reviews"},
    
    # Risk management
    {"name": "风险规则", "code": "risk:rule", "type": "button", "path": "/risks"},
    {"name": "风险项", "code": "risk:item", "type": "button", "path": "/risks"},
    
    # Workflow management
    {"name": "工作流定义", "code": "workflow:definition", "type": "button", "path": "/workflows"},
    {"name": "工作流实例", "code": "workflow:instance", "type": "button", "path": "/workflows"},
    
    # Report
    {"name": "报表查看", "code": "report:view", "type": "button", "path": "/reports"},
    {"name": "报表导出", "code": "report:export", "type": "button", "path": "/reports"},
    
    # System
    {"name": "系统配置", "code": "system:config", "type": "button", "path": "/system"},
    {"name": "审计日志", "code": "system:audit", "type": "button", "path": "/system"},
]

# Role-permission mapping
ROLE_PERMISSIONS = {
    "superadmin": [p["code"] for p in DEFAULT_PERMISSIONS],
    "admin": [
        "user:list", "user:create", "user:update",
        "contract:list", "contract:create", "contract:update", "contract:delete",
        "review:list", "review:assign",
        "risk:rule", "risk:item",
        "workflow:definition", "workflow:instance",
        "report:view",
        "system:config", "system:audit",
    ],
    "legal_manager": [
        "contract:list", "contract:update",
        "review:list", "review:assign", "review:execute", "review:opinion",
        "risk:rule", "risk:item",
        "workflow:instance",
        "report:view", "report:export",
    ],
    "legal_specialist": [
        "contract:list",
        "review:list", "review:execute", "review:opinion",
        "risk:item",
    ],
    "business_manager": [
        "contract:list", "contract:create", "contract:submit",
        "review:list",
        "report:view",
    ],
    "business_staff": [
        "contract:list", "contract:create", "contract:submit",
    ],
    "executive": [
        "contract:list",
        "review:list",
        "report:view",
    ],
}


async def init_default_data():
    """Initialize default data"""
    async with async_session_factory() as session:
        # Check if data already exists
        result = await session.execute(select(Role).limit(1))
        if result.scalar_one_or_none():
            print("Default data already exists")
            return
        
        print("Initializing default data...")
        
        # Create roles
        role_map = {}
        for role_data in DEFAULT_ROLES:
            role = Role(**role_data)
            session.add(role)
            await session.flush()
            role_map[role.code] = role.id
        
        # Create permissions
        permission_map = {}
        for perm_data in DEFAULT_PERMISSIONS:
            perm = Permission(**perm_data)
            session.add(perm)
            await session.flush()
            permission_map[perm.code] = perm.id
        
        # Create role-permission mappings
        for role_code, perm_codes in ROLE_PERMISSIONS.items():
            role_id = role_map.get(role_code)
            if role_id:
                for perm_code in perm_codes:
                    perm_id = permission_map.get(perm_code)
                    if perm_id:
                        role_perm = RolePermission(role_id=role_id, permission_id=perm_id)
                        session.add(role_perm)
        
        # Create default superadmin
        superadmin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            name="系统管理员",
            department="法务部",
            is_active=True,
            is_superuser=True,
        )
        session.add(superadmin)
        await session.flush()
        
        # Assign superadmin role
        user_role = UserRole(user_id=superadmin.id, role_id=role_map["superadmin"])
        session.add(user_role)
        
        await session.commit()
        print("Default data initialized successfully")
        print("Default admin: admin / admin123")


if __name__ == "__main__":
    from app.core.database import engine, Base
    
    async def main():
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Tables created")
        
        # Initialize data
        await init_default_data()
    
    asyncio.run(main())
