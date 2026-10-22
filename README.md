# ModuFlow (可插拔 AI 产品研发与运营工作流平台)

> **ModuFlow** = `Module`（模块化与可插拔）+ `Flow`（战略工序流）。
> 专为多产品矩阵设计的 AI 原生产研与运营平台：将顶层战略分解为可编排的产品工程，在每个模块内建立**人机协作讨论室**，并通过**结构化 Issue 驱动全流程质量闭环**。

---

## 核心设计理念

1. **战略驱动的顶层工程**：战略举措（Strategic Initiative）作为顶层调度器，统一协调多产品线、共享调研与跨产品依赖。
2. **工序模板化与产品可裁剪**：内置 13 模块完整研发、快速迭代（7模块）、紧急热修复（3模块）等流程模板，不同产品按需选用。
3. **模块即协作空间（Collaboration Space）**：每个模块拥有独立的人机多轮研讨流（会话）、不可变交付物产物库（SHA-256 快照）与四阶段状态机（`draft → discussing → reviewing → baselined`）。
4. **Issue 驱动跨模块质量门禁**：下游测试或运营发现问题，一键派发结构化 Bug/反馈到上游责任模块；Critical/Major 级别问题阻断基线锁定，倒逼质量闭环。

---

## 快速启动

### 依赖环境
- macOS / Linux / Windows
- Python 3.10+
- Node.js 18+

### 一键启动 (推荐)
在根目录下直接执行：
```bash
./run.sh
```
启动后访问：
- **Web 控制台**：[http://localhost:5173](http://localhost:5173)
- **FastAPI 接口文档 (Swagger)**：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 运行自动化测试

后端已包含完整的端到端切片单元测试（覆盖战略工程、模板实例化、人机对话、初稿生成、修改反馈、Bug 提报与基线门禁）：
```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_api.py -v
```

---

## 目录结构

```
ModuFlow/
├── backend/                  # FastAPI + SQLAlchemy 异步后端
│   ├── app/
│   │   ├── api/              # RESTful API 端点
│   │   ├── core/             # 配置、数据库、状态机
│   │   ├── models/           # 数据持久化实体
│   │   ├── schemas/          # Pydantic v2 契约模式
│   │   └── services/         # Agent 响应模拟、工作流引擎、Issue 路由
│   └── tests/                # 自动化测试用例
│
├── frontend/                 # React 18 + Vite + Tailwind CSS 前端
│   ├── src/
│   │   ├── components/       # 导航栏、状态标签、提报弹窗
│   │   ├── pages/            # 战略看板、13 模块视图、协作研讨室、Issue 看板
│   │   ├── services/         # API 请求客户端
│   │   └── types/            # TypeScript 统一接口定义
│   └── package.json
│
├── data/                     # 本地 SQLite 数据库与快照存储
├── docs/                     # 实施方案与详细规范文档
│   ├── MODUFLOW_SPEC.md      # 完整实施规范 (统一规范)
│   └── PHASE_1_PLAN.md       # 阶段 1 实施计划
└── run.sh                    # 一键并行启动脚本
```
