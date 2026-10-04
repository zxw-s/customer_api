# 客户销售统计模块

基于 FastAPI 实现的客户销售统计 RESTful API 服务，提供客户列表查询、按区域统计销售额、单客户订单查询等功能。

## 技术栈

| 组件 | 说明 |
|------|------|
| Python 3.10+ | 运行环境 |
| FastAPI | Web 框架 |
| Pydantic v2 | 参数校验与数据模型 |
| Decimal | 金额精确计算，避免 float 精度丢失 |
| pytest + httpx | 单元测试（28 个用例） |

## 快速启动

```bash
# 安装依赖
pip install fastapi uvicorn httpx pytest

# 启动服务（默认绑定 127.0.0.1:8000）
python customer_api.py

# 运行测试
pytest test_customer.py -v
```

启动后访问 http://127.0.0.1:8000/docs 可查看 Swagger 交互式文档。

---

## 鉴权

所有接口均需在 HTTP 请求头中携带 API Key：

```
X-API-Key: demo-api-key-2026
```

缺失或错误的 API Key 将返回 `403 Forbidden`。

**curl 示例**：

```bash
curl -H "X-API-Key: demo-api-key-2026" http://127.0.0.1:8000/customers
```

---

## 接口文档

### 1. 获取客户列表

**GET** `/customers`

返回客户列表，支持按区域筛选和分页。

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| region | string | 否 | — | `max_length=10` | 按区域筛选，可选值：`华东` / `华南` / `华北` / `西南` |
| skip | int | 否 | `0` | `ge=0` | 分页偏移量 |
| limit | int | 否 | `10` | `ge=1, le=100` | 每页返回数量 |

#### 响应示例

```json
{
  "total": 2,
  "items": [
    {
      "id": 1,
      "name": "张三科技有限公司",
      "region": "华东",
      "contact": "13800001111",
      "created_at": "2025-01-15"
    },
    {
      "id": 5,
      "name": "钱七网络科技",
      "region": "华东",
      "contact": "13500005555",
      "created_at": "2025-07-01"
    }
  ]
}
```

#### 错误响应

| 状态码 | 场景 |
|--------|------|
| 400 | 区域值不在可选范围内 |
| 403 | 缺失或错误的 API Key |
| 422 | 参数类型错误（如 skip 为负数、limit 超出范围） |

---

### 2. 按区域统计销售额

**GET** `/sales/by-region`

按区域汇总销售额和订单数，支持按日期范围过滤。结果按区域名称排序。

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| start_date | string | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 起始日期（含） |
| end_date | string | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 结束日期（含） |

#### 响应示例

```json
[
  {
    "region": "华东",
    "total_amount": 120500.0,
    "order_count": 4
  },
  {
    "region": "华南",
    "total_amount": 90000.0,
    "order_count": 4
  },
  {
    "region": "华北",
    "total_amount": 58500.0,
    "order_count": 2
  },
  {
    "region": "西南",
    "total_amount": 40000.0,
    "order_count": 2
  }
]
```

#### 错误响应

| 状态码 | 场景 |
|--------|------|
| 400 | 日期格式错误 / start_date 晚于 end_date |
| 403 | 缺失或错误的 API Key |

---

### 3. 查询单客户订单

**GET** `/customers/{customer_id}/orders`

查询指定客户的所有订单，支持按日期范围过滤。

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| customer_id | int | 是 | 客户唯一标识 |

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| start_date | string | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 起始日期（含） |
| end_date | string | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 结束日期（含） |

#### 响应示例

```json
[
  {
    "id": 101,
    "customer_id": 1,
    "product": "服务器A型",
    "amount": 50000.0,
    "order_date": "2025-02-10"
  },
  {
    "id": 102,
    "customer_id": 1,
    "product": "交换机B型",
    "amount": 12000.0,
    "order_date": "2025-03-15"
  }
]
```

#### 错误响应

| 状态码 | 场景 |
|--------|------|
| 400 | 日期格式错误 / start_date 晚于 end_date |
| 403 | 缺失或错误的 API Key |
| 404 | 客户 ID 不存在 |
| 422 | customer_id 类型错误（如传入字符串） |

---

## 日期格式说明

所有日期参数必须严格遵循 `YYYY-MM-DD` 格式，例如 `2025-06-15`。以下格式均会被拒绝：

- `2025/06/15`（斜杠分隔）
- `2025-6-15`（月/日未补零）
- `20250615`（无分隔符）

---

## 模拟数据说明

本模块使用内存模拟数据，包含：

- **6 个客户**：分布在华东(2)、华南(2)、华北(1)、西南(1) 四个区域
- **12 笔订单**：时间跨度 2025-02 ~ 2025-09，涉及服务器、交换机、防火墙、路由器四类产品的销售

---

## 项目结构

```
客户销售统计模块/
├── customer_api.py    # FastAPI 接口实现
├── test_customer.py   # 单元测试（28 个用例）
├── api_doc.md         # 完整 API 文档（入参/出参/错误码/示例）
├── CODE_REVIEW.md     # 代码审查报告
└── README.md          # 项目说明与接口概览
```
