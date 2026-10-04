# 客户销售统计系统 — API 文档

> 版本：1.0.0  
> 基础地址：`http://127.0.0.1:8000`  
> 协议：HTTP / JSON  
> 鉴权：API Key（请求头 `X-API-Key`）

---

## 一、通用说明

### 1.1 鉴权

所有接口均需在 HTTP 请求头中携带 API Key：

| 请求头 | 值 | 说明 |
|--------|-----|------|
| `X-API-Key` | `demo-api-key-2026` | 有效密钥，缺失或错误返回 403 |

示例：

```bash
curl -H "X-API-Key: demo-api-key-2026" http://127.0.0.1:8000/customers
```

### 1.2 通用错误码

| HTTP 状态码 | 含义 | 触发场景 |
|-------------|------|----------|
| 200 | 成功 | 请求正常处理 |
| 400 | 请求参数错误 | 日期格式错误、区域无效、日期范围颠倒 |
| 403 | 未授权 | 缺少 API Key 或密钥无效 |
| 404 | 资源不存在 | 客户 ID 不存在 |
| 422 | 请求体校验失败 | 参数类型错误、超出范围约束 |

### 1.3 通用错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 1.4 日期格式

所有日期参数必须严格遵循 `YYYY-MM-DD` 格式（如 `2025-06-15`），不接受 `2025/06/15` 或 `2025-6-15` 等变体。

---

## 二、数据模型

### 2.1 Customer（客户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 客户唯一标识 |
| `name` | `string` | 客户名称 |
| `region` | `string` | 所属区域：华东 / 华南 / 华北 / 西南 |
| `contact` | `string` | 联系方式（手机号） |
| `created_at` | `string` | 创建日期，格式 `YYYY-MM-DD` |

### 2.2 Order（订单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 订单唯一标识 |
| `customer_id` | `int` | 关联客户 ID |
| `product` | `string` | 产品名称 |
| `amount` | `float` | 订单金额（元），内部以 Decimal 精确计算 |
| `order_date` | `string` | 下单日期，格式 `YYYY-MM-DD` |

### 2.3 RegionSales（区域销售统计）

| 字段 | 类型 | 说明 |
|------|------|------|
| `region` | `string` | 区域名称 |
| `total_amount` | `float` | 该区域总销售额 |
| `order_count` | `int` | 该区域订单总数 |

### 2.4 PaginatedCustomers（客户分页响应）

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | `int` | 符合条件的客户总数 |
| `items` | `Customer[]` | 当前页客户列表 |

---

## 三、接口详情

### 3.1 获取客户列表

```
GET /customers
```

获取客户列表，支持按区域筛选和分页。

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| `region` | `string` | 否 | — | `max_length=10` | 按区域筛选，可选值：华东 / 华南 / 华北 / 西南 |
| `skip` | `int` | 否 | `0` | `ge=0` | 分页偏移量，跳过的记录数 |
| `limit` | `int` | 否 | `10` | `ge=1, le=100` | 每页返回数量 |

#### 响应

- **成功**：`200 OK`，返回 `PaginatedCustomers` 对象
- **参数错误**：`400 Bad Request`，`region` 值不在可选范围内
- **校验失败**：`422 Unprocessable Entity`，`skip`/`limit` 超出约束范围

#### 响应示例

**请求**：

```bash
curl -H "X-API-Key: demo-api-key-2026" \
     "http://127.0.0.1:8000/customers?region=华东&skip=0&limit=10"
```

**响应** `200 OK`：

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

**错误响应** `400 Bad Request`（无效区域）：

```json
{
  "detail": "无效的区域 '西北'，可选值: 华北, 华东, 华南, 西南"
}
```

**错误响应** `422 Unprocessable Entity`（limit=0）：

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be greater than or equal to 1",
      "input": "0"
    }
  ]
}
```

---

### 3.2 按区域统计销售额

```
GET /sales/by-region
```

按区域汇总销售额和订单数，支持按日期范围过滤。结果按区域名称排序。

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| `start_date` | `string` | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 起始日期（含） |
| `end_date` | `string` | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 结束日期（含） |

#### 响应

- **成功**：`200 OK`，返回 `RegionSales[]` 数组
- **参数错误**：`400 Bad Request`，日期格式错误或 `start_date` 晚于 `end_date`

#### 响应示例

**请求**：

```bash
curl -H "X-API-Key: demo-api-key-2026" \
     "http://127.0.0.1:8000/sales/by-region"
```

**响应** `200 OK`：

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

**请求**（带日期范围）：

```bash
curl -H "X-API-Key: demo-api-key-2026" \
     "http://127.0.0.1:8000/sales/by-region?start_date=2025-06-01&end_date=2025-06-30"
```

**响应** `200 OK`：

```json
[
  {
    "region": "华北",
    "total_amount": 8500.0,
    "order_count": 1
  }
]
```

**错误响应** `400 Bad Request`（日期格式错误）：

```json
{
  "detail": "start_date 格式错误，要求 YYYY-MM-DD，实际值: 2025/01/01"
}
```

**错误响应** `400 Bad Request`（日期范围颠倒）：

```json
{
  "detail": "start_date 不能晚于 end_date"
}
```

---

### 3.3 查询单客户订单

```
GET /customers/{customer_id}/orders
```

查询指定客户的所有订单，支持按日期范围过滤。

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `customer_id` | `int` | 是 | 客户 ID |

#### 请求参数（Query）

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| `start_date` | `string` | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 起始日期（含） |
| `end_date` | `string` | 否 | — | `max_length=10`，格式 `YYYY-MM-DD` | 结束日期（含） |

#### 响应

- **成功**：`200 OK`，返回 `Order[]` 数组
- **资源不存在**：`404 Not Found`，`customer_id` 不存在
- **参数错误**：`400 Bad Request`，日期格式错误或 `start_date` 晚于 `end_date`
- **校验失败**：`422 Unprocessable Entity`，`customer_id` 类型非整数

#### 响应示例

**请求**：

```bash
curl -H "X-API-Key: demo-api-key-2026" \
     "http://127.0.0.1:8000/customers/1/orders"
```

**响应** `200 OK`：

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

**请求**（带日期过滤）：

```bash
curl -H "X-API-Key: demo-api-key-2026" \
     "http://127.0.0.1:8000/customers/1/orders?start_date=2025-03-01&end_date=2025-03-31"
```

**响应** `200 OK`：

```json
[
  {
    "id": 102,
    "customer_id": 1,
    "product": "交换机B型",
    "amount": 12000.0,
    "order_date": "2025-03-15"
  }
]
```

**错误响应** `404 Not Found`（客户不存在）：

```json
{
  "detail": "客户ID 999 不存在"
}
```

**错误响应** `422 Unprocessable Entity`（customer_id 非整数）：

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["path", "customer_id"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "abc"
    }
  ]
}
```

---

## 四、错误码速查表

| 接口 | 200 | 400 | 403 | 404 | 422 |
|------|-----|-----|-----|-----|-----|
| `GET /customers` | 返回客户列表 | region 无效 | 无/错 API Key | — | skip/limit 越界 |
| `GET /sales/by-region` | 返回区域统计 | 日期格式错/范围颠倒 | 无/错 API Key | — | — |
| `GET /customers/{id}/orders` | 返回订单列表 | 日期格式错/范围颠倒 | 无/错 API Key | 客户不存在 | customer_id 非整数 |

---

## 五、模拟数据参考

### 客户数据（6 条）

| ID | 名称 | 区域 | 联系方式 | 创建日期 |
|----|------|------|----------|----------|
| 1 | 张三科技有限公司 | 华东 | 13800001111 | 2025-01-15 |
| 2 | 李氏集团 | 华南 | 13900002222 | 2025-03-20 |
| 3 | 王五贸易公司 | 华北 | 13700003333 | 2025-05-08 |
| 4 | 赵六电子商务 | 西南 | 13600004444 | 2025-06-12 |
| 5 | 钱七网络科技 | 华东 | 13500005555 | 2025-07-01 |
| 6 | 孙八信息技术 | 华南 | 13400006666 | 2025-08-18 |

### 订单数据（12 条）

| ID | 客户ID | 产品 | 金额 | 下单日期 |
|----|--------|------|------|----------|
| 101 | 1 | 服务器A型 | 50000 | 2025-02-10 |
| 102 | 1 | 交换机B型 | 12000 | 2025-03-15 |
| 103 | 2 | 服务器A型 | 50000 | 2025-04-01 |
| 104 | 2 | 防火墙C型 | 28000 | 2025-05-20 |
| 105 | 3 | 路由器D型 | 8500 | 2025-06-15 |
| 106 | 3 | 服务器A型 | 50000 | 2025-07-22 |
| 107 | 4 | 交换机B型 | 12000 | 2025-07-05 |
| 108 | 4 | 防火墙C型 | 28000 | 2025-08-10 |
| 109 | 5 | 服务器A型 | 50000 | 2025-08-01 |
| 110 | 5 | 路由器D型 | 8500 | 2025-09-12 |
| 111 | 6 | 防火墙C型 | 28000 | 2025-09-05 |
| 112 | 6 | 交换机B型 | 12000 | 2025-09-20 |
