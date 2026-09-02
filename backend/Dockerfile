FROM python:3.12-slim

WORKDIR /app

# 系统依赖 (腾讯云内网 apt 镜像加速)
RUN (sed -i 's|deb.debian.org|mirrors.tencentyun.com|g; s|security.debian.org|mirrors.tencentyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
    || sed -i 's|deb.debian.org|mirrors.tencentyun.com|g; s|security.debian.org|mirrors.tencentyun.com|g' /etc/apt/sources.list 2>/dev/null || true) \
    && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 先装 CPU 版 torch/torchvision (本地 wheel)
# 原因: pypi 默认 linux torch 是 CUDA 版, 会强拉 3.4G 的 nvidia/triton GPU 库, CPU 服务器用不到且会撑爆磁盘
# 先装好 CPU 版, 后续 easyocr/sentence-transformers 检测到 torch 已满足便不会再拉 GPU 版
COPY wheels/ /tmp/wheels/
RUN pip install --no-cache-dir --no-deps /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels \
    && pip show torch | grep -q "2.13.0+cpu" \
    && echo "torch CPU 版确认, 无 CUDA 库"

# Python依赖 (使用腾讯云内网镜像加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.tencentyun.com/pypi/simple \
    --trusted-host mirrors.tencentyun.com

# 应用代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
