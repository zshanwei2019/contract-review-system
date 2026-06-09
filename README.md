# 智能合同审查系统 (Intelligent Contract Review System)

企业级合同全生命周期管理平台，集成 AI 智能审查能力。

## 功能特性

### 合同管理
- 合同创建、编辑、版本管理
- 合同文件上传与管理
- 合同状态流转 (草稿 → 待审 → 审查中 → 已完成)
- 合同要素提取与结构化

### 智能审查
- AI 辅助合同风险识别
- 多人并行审查
- 审查意见管理
- 风险等级评估

### 工作流引擎
- 可配置的审批流程
- 多级审批支持
- 流程实例跟踪

### 风险管理
- 风险规则配置
- 风险分类管理
- 风险项目跟踪

### 权限管理
- RBAC 权限控制
- 7 种预设角色：超级管理员、法务经理、法务专员、业务经理、业务人员、高管、普通用户
- 25+ 细粒度权限

### 系统管理
- 用户管理
- 通知中心
- 审计日志
- 数据看板

## 技术栈

### 后端
- **语言**: Python 3.11+
- **框架**: FastAPI
- **数据库**: PostgreSQL (asyncpg)
- **缓存**: Redis
- **ORM**: SQLAlchemy 2.0 (async)
- **认证**: JWT
- **AI**: OpenAI / LangChain (可选)

### 前端
- **框架**: Vue 3 + TypeScript
- **UI**: Element Plus
- **状态**: Pinia
- **图表**: ECharts
- **构建**: Vite

### 部署
- Docker Compose 一键部署
- Nginx 反向代理

## 快速开始

### 本地开发

```bash
# 1. 启动数据库
brew services start postgresql@15
brew services start redis

# 2. 创建数据库
createdb contract_review

# 3. 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑配置
python -m app.core.init_data  # 初始化数据
uvicorn app.main:app --reload

# 4. 前端
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
docker-compose up -d
```

## 默认账号

- 用户名: `admin`
- 密码: `admin123`

## 项目结构

```
contract-review-system/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API 路由
│   │   ├── core/            # 核心配置
│   │   ├── models/          # 数据模型
│   │   ├── schemas/         # Pydantic 模型
│   │   └── main.py          # 入口
│   ├── alembic/             # 数据库迁移
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/             # API 调用
│   │   ├── components/      # 组件
│   │   ├── layouts/         # 布局
│   │   ├── router/          # 路由
│   │   ├── stores/          # 状态管理
│   │   ├── views/           # 页面
│   │   └── main.ts          # 入口
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API 文档

启动后端后访问: http://localhost:8000/docs

## 角色权限

| 角色 | 权限说明 |
|------|---------|
| superadmin | 超级管理员，拥有所有权限 |
| admin | 管理员，除系统配置外的所有权限 |
| legal_manager | 法务经理，管理合同审查和风险 |
| legal_specialist | 法务专员，执行合同审查 |
| business_manager | 业务经理，管理业务合同 |
| business_staff | 业务人员，提交和跟踪合同 |
| executive | 高管，查看报表和审批 |

## License

MIT
