# Hindsight 记忆引擎 — 本地私有化部署全记录

> 部署日期：2026-05-09 | 部署环境：Mac mini M4 (macOS)
> 架构：Ollama(qwen2.5:7b) + Hindsight Docker + PostgreSQL(嵌入式)

---

## 一、架构概述

```
┌─────────────────────────────────────────────────────────┐
│                     macOS 宿主机                         │
│                                                         │
│   ┌──────────────┐      ┌──────────────────────────┐    │
│   │   Ollama      │      │   Hindsight Docker        │    │
│   │  (qwen2.5:7b) ◄─────►   (localhost:8888)         │    │
│   │  0.0.0.0:11434│      │                          │    │
│   │               │      │  ┌──────────────────┐    │    │
│   │               │      │  │ PostgreSQL(嵌入式) │    │    │
│   │               │      │  │ (记忆持久化存储)  │    │    │
│   │               │      │  └──────────────────┘    │    │
│   └──────────────┘      │  ┌──────────────────┐    │    │
│                          │  │ Embedding/Reranker│    │    │
│                          │  │ (本地模型加载)    │    │    │
│                          │  └──────────────────┘    │    │
│                          └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 角色 | 说明 |
|------|------|------|
| **Ollama** | LLM 推理 | 运行 qwen2.5:7b 提供文本理解/生成能力 |
| **Hindsight** | 记忆引擎 | 仿生记忆系统，支持语义/BM25/图谱检索 |
| **bge-small-en-v1.5** | Embedding | 文本向量化（本地加载 133MB） |
| **cross-encoder** | Reranker | 搜索结果重排序（本地加载） |
| **PostgreSQL** | 持久化 | 嵌入式 PG，存储记忆图谱 |

### 数据流

```
用户输入 → Hindsight API
  ├─ Embedding 模型 → 向量化
  ├─ BM25 全文检索
  ├─ 图谱关系检索
  ├─ RRF 融合排序
  ├─ Cross-encoder 重排序
  └─ LLM 生成最终回答
```

---

## 二、实现原理

### 2.1 记忆模型

Hindsight 将记忆分为三种类型：

1. **observation**（观察）：原始事实，如"今天下雨了"
2. **experience**（经验）：抽象总结，如"老黄喜欢炒股"
3. **world**（世界知识）：客观事件，如"2026年5月9日部署了Hindsight"

记忆之间存在**图谱关系**（实体关联、时序关联、因果关联），查询时可沿关系链展开。

### 2.2 检索流程

```
recall(bank_id, query)
  │
  ├─ 1. 语义检索 (embedding 相似度)
  ├─ 2. BM25 全文检索 (关键词匹配)
  ├─ 3. 图谱检索 (关系链展开)
  │
  ├─ RRF 融合排序 (Reciprocal Rank Fusion)
  │
  ├─ Cross-encoder 重排序 (更精确的语义匹配)
  │
  └─ LLM 整合 → 返回最终结果 + trace
```

### 2.3 特性优势

- **向量 + 关键词 + 图谱三路检索**：比单纯向量检索更全面
- **本地全栈私有化**：所有组件均在本地运行，无需外网
- **Cross-encoder 重排序**：比纯向量检索更精准
- **Trace 模式**：可查看完整检索链路，便于调试

---

## 三、部署步骤（完整流程）

### 3.1 前置条件

```bash
# 需要已安装：
# - Docker Desktop (macOS)
# - Python 3.11+
# - Ollama (已拉取 qwen2.5:7b)
```

### 3.2 启动 Ollama（允许外部访问）

```bash
# 重启 Ollama，绑定 0.0.0.0 以便 Docker 容器访问
killall ollama
OLLAMA_HOST=0.0.0.0:11434 nohup ollama serve > /tmp/ollama.log 2>&1 &

# 验证
curl -s http://localhost:11434/api/tags
```

### 3.3 拉取并启动 Hindsight Docker

```bash
# 拉取镜像（~5.85GB）
docker pull ghcr.io/vectorize-io/hindsight:latest

# 启动容器
docker run -d --name hindsight \
  -p 8888:8888 \
  -e HINDSIGHT_API_PORT=8888 \
  -e HINDSIGHT_API_HOST=0.0.0.0 \
  -e HINDSIGHT_API_LLM_PROVIDER=ollama \
  -e HINDSIGHT_API_LLM_MODEL=qwen2.5:7b \
  -e HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:11434/v1 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e HINDSIGHT_API_LOG_LEVEL=info \
  -e TRANSFORMERS_VERBOSITY=error \
  -e HF_HUB_OFFLINE=1 \
  ghcr.io/vectorize-io/hindsight:latest

# 检查启动日志（首次启动约 40-60 秒）
docker logs -f hindsight
```

### 3.4 安装客户端

```bash
pip3 install hindsight-client
```

### 3.5 设置自动重启

```bash
docker update --restart unless-stopped hindsight
```

---

## 四、使用方式

### 4.1 Python 客户端

```python
from hindsight_client import Hindsight

# 初始化客户端
client = Hindsight(base_url='http://localhost:8888')

# ── 存入记忆 ──
result = client.retain(
    bank_id='default',
    content='要记住的内容文本',
    # 可选参数：
    # metadata={'key': 'value'},  # 元数据标签
    # tags=['important', 'work'],  # 标签
    # timestamp=datetime.now(),    # 指定时间
)
print(result)  # RetainResponse(success=True, ...)

# ── 召回记忆 ──
result = client.recall(
    bank_id='default',
    query='查询问题，如"老黄是谁？"',
    # 可选参数：
    # max_tokens=4096,          # 最大 token 数
    # budget='mid',             # 检索预算: 'low'/'mid'/'high'
    # trace=True,               # 开启 trace（调试用）
)
print(result.results)  # 返回匹配的记忆列表

# ── 管理银行（bank）──
# bank = client.bank  # 可进一步管理
```

### 4.2 关键参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `ban k_id` | 记忆仓库名称（可隔离不同领域） | `default` |
| `budget` | 检索预算（low/mid/high） | `mid` |
| `max_tokens` | 返回结果最大 token 数 | 4096 |
| `trace` | 是否返回完整检索链路 | `False` |
| `tags` | 按标签过滤记忆 | 无 |
| `retain_async` | 异步存储（不等待完成） | `False` |

### 4.3 响应示例

```python
# retain 返回
{
    'success': True,
    'items_count': 1,
    'usage': TokenUsage(input_tokens=2107, output_tokens=257)
}

# recall 返回（启用 trace 时）
{
    'results': [
        RecallResult(id='xxx', type='experience',
                     text='老黄喜欢炒股和编程', ...),
        RecallResult(id='yyy', type='world',
                     text='部署了Hindsight记忆引擎', ...)
    ],
    'trace': {
        'query': {...},          # 查询 embedding
        'retrieval_results': [], # 三路检索结果
        'rrf_merged': [],        # RRF 融合
        'reranked': [],          # 重排序
        'summary': {}            # 总体统计
    }
}
```

---

## 五、环境变量参考

### Hindsight 关键环境变量

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `HINDSIGHT_API_PORT` | API 端口 | `8888` |
| `HINDSIGHT_API_HOST` | 绑定地址 | `0.0.0.0` |
| `HINDSIGHT_API_LLM_PROVIDER` | LLM 提供方 | `ollama` |
| `HINDSIGHT_API_LLM_MODEL` | LLM 模型名 | `qwen2.5:7b` |
| `HINDSIGHT_API_LLM_BASE_URL` | LLM API 地址 | `http://host.docker.internal:11434/v1` |
| `HINDSIGHT_API_LOG_LEVEL` | 日志级别 | `info` / `debug` |

### 排错关键变量

| 变量 | 作用 | 值 |
|------|------|-----|
| `HF_HUB_OFFLINE=1` | 禁止从 HuggingFace 下载模型 | 离线加载缓存 |
| `TRANSFORMERS_VERBOSITY=error` | 减少 Transformers 日志 | 仅显示错误 |

---

## 六、常见问题排查

### Q1: 容器启动后 API 连不上 (Connection refused)

**原因**：sentence-transformers 加载 bge-small-en-v1.5 模型时阻塞了 Uvicorn 启动
**解决**：等待 60-90 秒，模型加载完成后服务自动可用

### Q2: LLM 验证失败 404

**原因**：`base_url` 没加 `/v1` 路径（Ollama 的 OpenAI 兼容 API 在 `/v1/` 下）
**解决**：设置 `HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:11434/v1`

### Q3: API 返回 Connection reset

**原因**：Embedding 模型首次加载时 HuggingFace 下载超时
**解决**：设置 `HF_HUB_OFFLINE=1` 并使用已缓存的模型文件

### Q4: Ollama Docker 容器内无法访问

**原因**：Ollama 默认绑定 127.0.0.1，Docker 只能访问 0.0.0.0
**解决**：用 `OLLAMA_HOST=0.0.0.0:11434` 重启 Ollama

### Q5: Embedding 模型下载慢

**解决**：使用代理或预先下载模型到容器缓存：
```bash
# 确保缓存目录存在
docker exec hindsight ls -la /home/hindsight/.cache/huggingface/
```

---

## 七、性能参考

| 操作 | 耗时（首次） | 耗时（后续） | 备注 |
|------|-------------|-------------|------|
| Docker 镜像拉取 | ~5-10 min | - | 5.85GB |
| 容器首次启动 | ~60-90s | ~40s | 含模型加载 |
| retain (存入) | ~5-10s | ~2-3s | 含LLM处理 |
| recall (召回) | ~0.5-2s | ~0.3s | 含检索+重排序 |
| 模型加载到GPU | ~40s | - | qwen2.5:7b |

---

## 八、完整运行状态验证

```bash
# 1. 检查容器状态
docker ps | grep hindsight

# 2. 检查 Ollama 状态
curl -s http://localhost:11434/api/tags

# 3. 检查 Hindsight API
curl -s http://localhost:8888/

# 4. 测试记忆功能
python3 -c "
from hindsight_client import Hindsight
client = Hindsight(base_url='http://localhost:8888')

# 存入
r1 = client.retain(bank_id='default', content='测试记忆')
print('Retain:', r1.success)

# 召回
r2 = client.recall(bank_id='default', query='测试')
print('Recall:', [r.text for r in r2.results])
"
```

---

*本文档由 H（赛博黑猫）于 2026-05-09 在部署过程中编写*
*基于 Hindsight v0.6.1 + Ollama qwen2.5:7b*
