# e2bridge

将 [cto.new](https://cto.new) (EngineLabs) API 转换为 OpenAI API 格式的代理服务。

## 功能

- 将 cto.new API 转换为 OpenAI `/v1/chat/completions` 格式
- 支持流式响应
- 自动刷新 JWT token
- 对话历史缓存

## 部署

### 前置要求

- Python 3.14+
- 访问 cto.new 的网络环境

### 安装步骤

1. 克隆项目

```bash
git clone <repository-url>
cd e2bridge
```

2. 安装依赖

使用 pip (推荐):

```bash
pip install .
```

或者开发模式安装:

```bash
pip install -e .
```

3. 配置环境变量

复制 `.env.example` 为 `.env` 并编辑：

```env
API_MASTER_KEY=your_api_key_here
CLERK_COOKIE=your_clerk_cookie_here
CLERK_SESSION_ID=sess_xxx
CLERK_ORGANIZATION_ID=org_xxx
```

### 获取 Clerk 认证信息

1. 在浏览器中登录 [cto.new](https://cto.new)
2. 打开开发者工具 (F12)
3. 切换到 Network 标签
4. 刷新页面
5. 找到发往 `https://clerk.cto.new/v1/client/sessions/sess_XXX/tokens` 的请求

**获取 CLERK_COOKIE:**
- 在 Request Headers 中找到 `cookie` 字段，复制完整值

**获取 CLERK_SESSION_ID:**
- 在请求 URL 中查找类似 `sess_xxxxx` 的值

**获取 CLERK_ORGANIZATION_ID:**
- 在请求 Payload 中查找 `organization_id` 字段

### 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 测试可用性

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"messages\": [{\"content\": \"hello\"}]}" http://127.0.0.1:8000/v1/chat/completions --output -
```

## 使用

在支持 OpenAI API 的客户端中配置：

- API 地址: `http://your-server:8000`
- API 密钥: 在 `.env` 中设置的 `API_MASTER_KEY`
- 模型: cto.new 支持的模型（如 `ClaudeSonnet4_5`, `GPT5` 等）

## License

Apache License 2.0
