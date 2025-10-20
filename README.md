# e2bridge

将 [cto.new](https://cto.new) (EngineLabs) API 转换为 OpenAI API 格式的代理服务。

## 功能

- 将 cto.new API 转换为 OpenAI `/v1/chat/completions` 格式
- 支持流式响应
- 自动刷新 JWT token
- 对话历史缓存

## 部署

### 前置要求

- Python 3.10+
- 访问 cto.new 的网络环境

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd e2bridge
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量

复制 `.env.example` 为 `.env` 并编辑：

```env
API_MASTER_KEY=your_api_key_here
CLERK_COOKIE="your_clerk_cookie_here"
```

### 获取 CLERK_COOKIE

1. 在浏览器中登录 [cto.new](https://cto.new)
2. 打开开发者工具 (F12)
3. 切换到 Network 标签
4. 在页面中进行操作（如发送消息）
5. 找到发往 `clerk.cto.new` 的请求
6. 在 Request Headers 中复制 `cookie` 字段的值

### 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 使用

在支持 OpenAI API 的客户端中配置：

- API 地址: `http://your-server:8000`
- API 密钥: 在 `.env` 中设置的 `API_MASTER_KEY`
- 模型: cto.new 支持的模型（如 `ClaudeSonnet4_5`, `GPT5` 等）

## 项目结构

```
e2bridge/
├── main.py                 # FastAPI 主入口
├── requirements.txt        # 依赖列表
├── .env.example           # 环境变量模板
└── app/
    ├── core/
    │   └── config.py      # 配置管理
    ├── providers/
    │   ├── base_provider.py
    │   └── enginelabs_provider.py  # cto.new API 交互
    └── utils/
        └── sse_utils.py   # SSE 工具函数
```

## 注意事项

- 依赖 cto.new 和 Clerk 的接口稳定性
- 需要手动获取 CLERK_COOKIE
- 对话历史缓存基于内存，重启后丢失

## License

Apache License 2.0
