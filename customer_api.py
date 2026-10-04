# -*- coding: utf-8 -*-
"""
客户销售统计模块 - FastAPI 接口实现

提供客户列表查询、按区域统计销售额、单客户订单查询等功能。
使用内存模拟数据，无需外部数据库依赖。
"""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import FastAPI, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, PlainSerializer

# 金额类型：内部用 Decimal 精确计算，JSON 序列化为 float
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]

# ============================================================
# 数据模型定义
# ============================================================


class Customer(BaseModel):
    """客户信息模型"""
    id: int = Field(..., description="客户唯一标识")
    name: str = Field(..., description="客户名称")
    region: str = Field(..., description="所属区域（华东/华南/华北/西南）")
    contact: str = Field(..., description="联系方式")
    created_at: str = Field(..., description="创建日期")


class Order(BaseModel):
    """订单信息模型"""
    id: int = Field(..., description="订单唯一标识")
    customer_id: int = Field(..., description="关联客户ID")
    product: str = Field(..., description="产品名称")
    amount: Money = Field(..., ge=0, description="订单金额（元）")
    order_date: str = Field(..., description="下单日期 YYYY-MM-DD")


class RegionSales(BaseModel):
    """区域销售额统计结果"""
    region: str = Field(..., description="区域名称")
    total_amount: Money = Field(..., description="该区域总销售额")
    order_count: int = Field(..., description="该区域订单总数")


class PaginatedCustomers(BaseModel):
    """客户列表分页响应"""
    total: int = Field(..., description="客户总数")
    items: list[Customer] = Field(..., description="当前页客户列表")


# ============================================================
# 模拟数据
# ============================================================

CUSTOMERS: list[dict] = [
    {"id": 1, "name": "张三科技有限公司", "region": "华东", "contact": "13800001111", "created_at": "2025-01-15"},
    {"id": 2, "name": "李氏集团", "region": "华南", "contact": "13900002222", "created_at": "2025-03-20"},
    {"id": 3, "name": "王五贸易公司", "region": "华北", "contact": "13700003333", "created_at": "2025-05-08"},
    {"id": 4, "name": "赵六电子商务", "region": "西南", "contact": "13600004444", "created_at": "2025-06-12"},
    {"id": 5, "name": "钱七网络科技", "region": "华东", "contact": "13500005555", "created_at": "2025-07-01"},
    {"id": 6, "name": "孙八信息技术", "region": "华南", "contact": "13400006666", "created_at": "2025-08-18"},
]

ORDERS: list[dict] = [
    {"id": 101, "customer_id": 1, "product": "服务器A型", "amount": Decimal("50000.00"), "order_date": "2025-02-10"},
    {"id": 102, "customer_id": 1, "product": "交换机B型", "amount": Decimal("12000.00"), "order_date": "2025-03-15"},
    {"id": 103, "customer_id": 2, "product": "服务器A型", "amount": Decimal("50000.00"), "order_date": "2025-04-01"},
    {"id": 104, "customer_id": 2, "product": "防火墙C型", "amount": Decimal("28000.00"), "order_date": "2025-05-20"},
    {"id": 105, "customer_id": 3, "product": "路由器D型", "amount": Decimal("8500.00"), "order_date": "2025-06-15"},
    {"id": 106, "customer_id": 3, "product": "服务器A型", "amount": Decimal("50000.00"), "order_date": "2025-07-22"},
    {"id": 107, "customer_id": 4, "product": "交换机B型", "amount": Decimal("12000.00"), "order_date": "2025-07-05"},
    {"id": 108, "customer_id": 4, "product": "防火墙C型", "amount": Decimal("28000.00"), "order_date": "2025-08-10"},
    {"id": 109, "customer_id": 5, "product": "服务器A型", "amount": Decimal("50000.00"), "order_date": "2025-08-01"},
    {"id": 110, "customer_id": 5, "product": "路由器D型", "amount": Decimal("8500.00"), "order_date": "2025-09-12"},
    {"id": 111, "customer_id": 6, "product": "防火墙C型", "amount": Decimal("28000.00"), "order_date": "2025-09-05"},
    {"id": 112, "customer_id": 6, "product": "交换机B型", "amount": Decimal("12000.00"), "order_date": "2025-09-20"},
]

# ============================================================
# FastAPI 应用初始化
# ============================================================

app = FastAPI(
    title="客户销售统计系统",
    description="提供客户管理、区域销售统计、订单查询等接口",
    version="1.0.0",
)

# ============================================================
# 模块级常量（避免每次请求重复构建）
# ============================================================

VALID_REGIONS: frozenset[str] = frozenset({"华东", "华南", "华北", "西南"})
_CID_TO_REGION: dict[int, str] = {c["id"]: c["region"] for c in CUSTOMERS}
_CUSTOMER_IDS: set[int] = {c["id"] for c in CUSTOMERS}
_DATE_RE: re.Pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ============================================================
# API Key 鉴权
# ============================================================

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_VALID_API_KEYS: set[str] = {"demo-api-key-2026"}


async def _verify_api_key(key: Optional[str] = Security(_API_KEY_HEADER)) -> str:
    """校验请求头中的 API Key，无效或缺失时返回 403"""
    if key is None or key not in _VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="API Key 缺失或无效")
    return key

# ============================================================
# 辅助函数
# ============================================================


def _parse_date(date_str: Optional[str], field_name: str) -> Optional[date]:
    """将日期字符串解析为 date 对象，严格校验 YYYY-MM-DD 格式"""
    if date_str is None:
        return None
    if not _DATE_RE.match(date_str):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} 格式错误，要求 YYYY-MM-DD，实际值: {date_str}",
        )
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} 日期无效: {date_str}",
        )


def _filter_orders_by_date(
    orders: list[dict],
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[dict]:
    """根据起止日期过滤订单列表，每条订单的日期只解析一次"""
    if start_date is None and end_date is None:
        return orders
    parsed = [
        (o, date.fromisoformat(o["order_date"]))
        for o in orders
    ]
    result = []
    for order, d in parsed:
        if start_date is not None and d < start_date:
            continue
        if end_date is not None and d > end_date:
            continue
        result.append(order)
    return result


# ============================================================
# 接口定义
# ============================================================


@app.get("/customers", response_model=PaginatedCustomers, summary="获取客户列表", dependencies=[Security(_verify_api_key)])
def get_customers(
    region: Optional[str] = Query(None, description="按区域筛选：华东/华南/华北/西南", max_length=10),
    skip: int = Query(0, ge=0, description="跳过的记录数（分页偏移）"),
    limit: int = Query(10, ge=1, le=100, description="每页返回数量，1~100"),
):
    """
    获取客户列表，支持按区域筛选和分页。

    - **region**: 可选，按区域过滤客户
    - **skip**: 分页偏移量，默认 0
    - **limit**: 每页数量，默认 10，最大 100
    """
    if region is not None and region not in VALID_REGIONS:
        raise HTTPException(
            status_code=400,
            detail=f"无效的区域 '{region}'，可选值: {', '.join(sorted(VALID_REGIONS))}",
        )

    # 按区域过滤
    filtered = CUSTOMERS
    if region is not None:
        filtered = [c for c in filtered if c["region"] == region]

    total = len(filtered)
    items = filtered[skip: skip + limit]

    return PaginatedCustomers(
        total=total,
        items=[Customer(**c) for c in items],
    )


@app.get("/sales/by-region", response_model=list[RegionSales], summary="按区域统计销售额", dependencies=[Security(_verify_api_key)])
def get_sales_by_region(
    start_date: Optional[str] = Query(None, description="起始日期（含），格式 YYYY-MM-DD", max_length=10),
    end_date: Optional[str] = Query(None, description="结束日期（含），格式 YYYY-MM-DD", max_length=10),
):
    """
    按区域汇总销售额和订单数，支持按日期范围过滤。

    - **start_date**: 可选，起始日期
    - **end_date**: 可选，结束日期
    """
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    if sd is not None and ed is not None and sd > ed:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    filtered_orders = _filter_orders_by_date(ORDERS, sd, ed)

    region_stats: dict[str, dict] = {}
    for order in filtered_orders:
        reg = _CID_TO_REGION.get(order["customer_id"])
        if reg is None:
            continue
        if reg not in region_stats:
            region_stats[reg] = {"total_amount": Decimal("0"), "order_count": 0}
        region_stats[reg]["total_amount"] += order["amount"]
        region_stats[reg]["order_count"] += 1

    # 转为响应列表，按区域名称排序
    return [
        RegionSales(region=reg, total_amount=vals["total_amount"], order_count=vals["order_count"])
        for reg, vals in sorted(region_stats.items())
    ]


@app.get("/customers/{customer_id}/orders", response_model=list[Order], summary="查询单客户订单", dependencies=[Security(_verify_api_key)])
def get_customer_orders(
    customer_id: int,
    start_date: Optional[str] = Query(None, description="起始日期（含），格式 YYYY-MM-DD", max_length=10),
    end_date: Optional[str] = Query(None, description="结束日期（含），格式 YYYY-MM-DD", max_length=10),
):
    """
    查询指定客户的所有订单，支持按日期范围过滤。

    - **customer_id**: 客户ID（路径参数）
    - **start_date**: 可选，起始日期
    - **end_date**: 可选，结束日期
    """
    if customer_id not in _CUSTOMER_IDS:
        raise HTTPException(status_code=404, detail=f"客户ID {customer_id} 不存在")

    # 日期参数解析与校验
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    if sd is not None and ed is not None and sd > ed:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")

    # 筛选该客户的订单
    customer_orders = [o for o in ORDERS if o["customer_id"] == customer_id]

    # 按日期过滤
    customer_orders = _filter_orders_by_date(customer_orders, sd, ed)

    return [Order(**o) for o in customer_orders]


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
