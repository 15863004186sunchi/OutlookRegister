# OutlookRegister - 注册机 Docker 镜像
# 基于 Python 3.11 + Patchright (带 Chromium)

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# 安装 Chromium 运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础库
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libwayland-client0 \
    # 字体
    fonts-liberation fonts-noto-cjk \
    # 工具
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install requests

# 安装 Patchright 浏览器
RUN python -m patchright install chromium

# 复制应用代码
COPY . .

# 创建结果目录
RUN mkdir -p /app/Results

# 默认启动注册脚本
CMD ["python", "OutlookRegister_patchright.py"]
