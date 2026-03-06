# Boss 直聘 MCP 服务器 Dockerfile
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（Playwright 需要）
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器
RUN playwright install chromium
RUN playwright install-deps chromium

# 复制应用代码
COPY boss_zhipin_fastmcp_v2.py .
COPY login_verifier.py .

# 创建静态文件目录
RUN mkdir -p static

# 暴露端口
EXPOSE 8000

# 运行服务器
CMD ["python", "boss_zhipin_fastmcp_v2.py"]
