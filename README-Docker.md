# 合同审查系统 - Docker 部署

## 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 2. 启动服务
docker-compose up -d --build

# 3. 访问
# 前端: http://localhost:3001
# API: http://localhost:8000
```

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| backend | 8000 | FastAPI 后端 (Python 3.12) |
| frontend | 3001 | Nginx 静态前端 |

## 常用命令

```bash
# 查看日志
docker-compose logs -f backend

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 重建并启动
docker-compose up -d --build
```

## OCR 支持

默认使用 EasyOCR（中文+英文），首次运行会自动下载模型（约100MB）。

## 数据库

连接本地 PostgreSQL，使用 `host.docker.internal` 访问宿主机。
确保 PostgreSQL 已创建 `contract_review` 数据库。
