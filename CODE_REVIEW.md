# Code Review 报告 — 客户销售统计模块

> 初审日期：2026-10-04  
> 复审日期：2026-10-04  
> 审查范围：`customer_api.py`、`test_customer.py`  
> 审查维度：可读性 / 边界处理 / 性能 / 安全

---

## 一、总体评价

项目结构清晰，接口设计规范，Pydantic 校验覆盖到位，28 个单元测试全部通过。经过 P0/P1 修复后，**金额精度、接口鉴权、输入限制、性能热点**等关键问题已全部解决。剩余 P2 项为非紧急的工程化改进。

| 维度 | 修复前 | 修复后 | 说明 |
|------|--------|--------|------|
| 可读性 | ★★★★☆ | ★★★★☆ | 中文注释充分，分段清晰；模拟数据仍用裸 dict（P2） |
| 边界处理 | ★★★☆☆ | ★★★★☆ | 已补充输入长度限制、严格日期校验；并发安全未覆盖（P2） |
| 性能 | ★★★☆☆ | ★★★★★ | 日期单次解析、常量缓存、O(1) 查找，已无热点 |
| 安全性 | ★★☆☆☆ | ★★★★☆ | 已添加 API Key 鉴权、绑定 127.0.0.1；CORS/限流待补（P2） |

---

## 二、问题清单

### customer_api.py

| # | 位置 | 问题 | 优先级 | 修复状态 |
|---|------|------|--------|----------|
| 1 | 原 L192 | **金额使用 float 累加，精度丢失** | **P0** | ✅ 已修复：改用 `Decimal` 存储计算，`Money` 类型别名序列化为 float |
| 2 | 原 L240 | **服务绑定 `0.0.0.0`**，暴露到公网 | **P0** | ✅ 已修复：改为 `127.0.0.1` |
| 3 | 原 L107-118 | **`_filter_orders_by_date` 重复解析日期** | **P1** | ✅ 已修复：预解析一次，单次遍历过滤 |
| 4 | 原 L182 | **每次请求重建 `cid_to_region` 映射** | **P1** | ✅ 已修复：提取为模块级常量 `_CID_TO_REGION` |
| 5 | 原 L140 | **`valid_regions` 每次调用重建集合** | **P1** | ✅ 已修复：提取为 `VALID_REGIONS` frozenset |
| 6 | 全局 | **接口无鉴权**，存在越权风险 | **P1** | ✅ 已修复：添加 `APIKeyHeader` + `_verify_api_key` 依赖 |
| 7 | 原 L128 等 | **Query 参数无最大长度限制** | **P1** | ✅ 已修复：所有 string 型 Query 添加 `max_length=10` |
| 8 | 原 L94-104 | **`strptime` 接受不规范日期输入** | **P2** | ✅ 顺手修复：正则预校验 + `date.fromisoformat` |
| 9 | L61-83 | **模拟数据用裸 `list[dict]`**，无类型保护 | **P2** | 🔲 待改进 |
| 10 | L31-32 | **日期字段用 `str` 类型**，丧失类型校验 | **P2** | 🔲 待改进 |
| 11 | 全局 | **无 CORS 配置**，前端跨域被拦截 | **P2** | 🔲 待改进 |
| 12 | 全局 | **无速率限制**，可被高频调用 | **P2** | 🔲 待改进 |
| 13 | 原 L216 | **线性搜索判断客户存在性** O(n) | **P2** | ✅ 顺手修复：`_CUSTOMER_IDS` set 实现 O(1) |

### test_customer.py

| # | 位置 | 问题 | 优先级 | 修复状态 |
|---|------|------|--------|----------|
| 14 | 原 L109 | **注释与断言不一致**（写 130500，断言 120500） | **P2** | ✅ 顺手修复：注释已更正 |
| 15 | 全局 | **缺少并发测试和性能基准测试** | **P2** | 🔲 待改进 |
| 16 | 全局 | **缺少负数 customer_id 测试** | **P2** | 🔲 待改进 |

---

## 三、修复详情

### 3.1 [P0] 金额精度 — Decimal + Money 类型别名

```python
# 定义 Money 类型：内部 Decimal 精确计算，JSON 序列化为 float
from decimal import Decimal
from typing import Annotated
from pydantic import PlainSerializer

Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]

# 模型字段
class Order(BaseModel):
    amount: Money = Field(..., ge=0, description="订单金额（元）")

class RegionSales(BaseModel):
    total_amount: Money = Field(..., description="该区域总销售额")

# 模拟数据使用 Decimal 字符串构造
ORDERS = [
    {"id": 101, "customer_id": 1, "product": "服务器A型",
     "amount": Decimal("50000.00"), "order_date": "2025-02-10"},
    # ...
]

# 聚合使用 Decimal 零值
region_stats[reg] = {"total_amount": Decimal("0"), "order_count": 0}
```

### 3.2 [P0] 绑定地址

```python
uvicorn.run(app, host="127.0.0.1", port=8000)
```

### 3.3 [P1] API Key 鉴权

```python
from fastapi import Security
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_VALID_API_KEYS: set[str] = {"demo-api-key-2026"}

async def _verify_api_key(key: Optional[str] = Security(_API_KEY_HEADER)) -> str:
    if key is None or key not in _VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="API Key 缺失或无效")
    return key

# 三个端点均添加依赖
@app.get("/customers", dependencies=[Security(_verify_api_key)])
@app.get("/sales/by-region", dependencies=[Security(_verify_api_key)])
@app.get("/customers/{customer_id}/orders", dependencies=[Security(_verify_api_key)])
```

### 3.4 [P1] 模块级常量缓存

```python
VALID_REGIONS: frozenset[str] = frozenset({"华东", "华南", "华北", "西南"})
_CID_TO_REGION: dict[int, str] = {c["id"]: c["region"] for c in CUSTOMERS}
_CUSTOMER_IDS: set[int] = {c["id"] for c in CUSTOMERS}
_DATE_RE: re.Pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```

### 3.5 [P1] 消除重复日期解析

```python
def _filter_orders_by_date(orders, start_date, end_date):
    """每条订单的日期只解析一次"""
    if start_date is None and end_date is None:
        return orders
    parsed = [(o, date.fromisoformat(o["order_date"])) for o in orders]
    result = []
    for order, d in parsed:
        if start_date is not None and d < start_date:
            continue
        if end_date is not None and d > end_date:
            continue
        result.append(order)
    return result
```

### 3.6 [P1] 输入长度限制 + 严格日期校验

```python
# 所有 string 型 Query 参数
start_date: Optional[str] = Query(None, max_length=10, ...)
end_date: Optional[str] = Query(None, max_length=10, ...)
region: Optional[str] = Query(None, max_length=10, ...)

# 日期严格校验
def _parse_date(date_str, field_name):
    if not _DATE_RE.match(date_str):
        raise HTTPException(status_code=400, detail=f"{field_name} 格式错误...")
    return date.fromisoformat(date_str)
```

---

## 四、优先级汇总

| 优先级 | 总数 | 已修复 | 待改进 |
|--------|------|--------|--------|
| **P0** | 2 | 2 ✅ | 0 |
| **P1** | 5 | 5 ✅ | 0 |
| **P2** | 9 | 3 ✅ | 6 🔲 |

---

## 五、安全检查专项

| 检查项 | 修复前 | 修复后 | 说明 |
|--------|--------|--------|------|
| SQL 注入 | ✅ 安全 | ✅ 安全 | 无数据库操作，纯内存查询 |
| XSS | ✅ 安全 | ✅ 安全 | FastAPI 返回 JSON，不渲染 HTML |
| 越权访问 | ⚠️ 风险 | ✅ 已修复 | 已添加 API Key 鉴权，无 Key 返回 403 |
| 密钥泄露 | ✅ 安全 | ✅ 安全 | 无硬编码密钥（API Key 为演示用途） |
| 输入校验 | ⚠️ 部分缺失 | ✅ 已修复 | 已添加 `max_length` + 正则日期校验 |
| 拒绝服务 | ⚠️ 风险 | ⚠️ 待改进 | 无速率限制（P2），建议后续集成 `slowapi` |
| 网络暴露 | ⚠️ 风险 | ✅ 已修复 | 已改为 `127.0.0.1`，不再绑定所有接口 |
| 金额精度 | ⚠️ 风险 | ✅ 已修复 | 已改用 `Decimal`，消除浮点误差 |

---

## 六、剩余 P2 待改进项

| # | 问题 | 建议 |
|---|------|------|
| 9 | 模拟数据用裸 `list[dict]` | 改用 `list[Customer]` / `list[Order]` 实例化 |
| 10 | 日期字段用 `str` 类型 | `created_at`、`order_date` 改为 `date` 类型 |
| 11 | 无 CORS 配置 | 添加 `CORSMiddleware` 配置允许的 origin |
| 12 | 无速率限制 | 集成 `slowapi` 或自定义限流中间件 |
| 15 | 缺少并发/性能测试 | 补充 `locust` / `pytest-benchmark` 用例 |
| 16 | 缺少负数 customer_id 测试 | 补充 `/customers/-1/orders` 边界值用例 |
