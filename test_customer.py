# -*- coding: utf-8 -*-
"""
客户销售统计模块 - 单元测试

使用 pytest + httpx.TestClient 对三个接口进行全面测试，
覆盖正常流程、参数校验、边界条件、鉴权和异常场景。
"""

import pytest
from fastapi.testclient import TestClient

from customer_api import app

# 测试用 API Key，与 customer_api._VALID_API_KEYS 一致
_TEST_API_KEY = "demo-api-key-2026"
_AUTH_HEADERS = {"X-API-Key": _TEST_API_KEY}


@pytest.fixture
def client():
    """创建携带有效 API Key 的测试客户端"""
    return TestClient(app)


@pytest.fixture
def anon_client():
    """创建不携带 API Key 的测试客户端（用于鉴权测试）"""
    return TestClient(app)


# ============================================================
# 鉴权测试
# ============================================================


class TestAuthentication:
    """API Key 鉴权测试集"""

    def test_无密钥返回403(self, anon_client):
        """不携带 X-API-Key 请求应返回 403"""
        resp = anon_client.get("/customers")
        assert resp.status_code == 403
        assert "API Key" in resp.json()["detail"]

    def test_错误密钥返回403(self, anon_client):
        """携带无效 API Key 应返回 403"""
        resp = anon_client.get("/customers", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_正确密钥返回200(self, client):
        """携带有效 API Key 应正常访问"""
        resp = client.get("/customers", headers=_AUTH_HEADERS)
        assert resp.status_code == 200

    def test_三个接口均需鉴权(self, anon_client):
        """三个接口在无 Key 时都应返回 403"""
        for path in ["/customers", "/sales/by-region", "/customers/1/orders"]:
            resp = anon_client.get(path)
            assert resp.status_code == 403, f"{path} 未鉴权但仍返回 {resp.status_code}"


# ============================================================
# /customers 客户列表接口测试
# ============================================================


class TestGetCustomers:
    """客户列表接口测试集"""

    def test_返回全部客户(self, client):
        """默认请求应返回所有 6 个客户"""
        resp = client.get("/customers", headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 6

    def test_按区域筛选_华东(self, client):
        """筛选华东区域，应返回 2 个客户"""
        resp = client.get("/customers", params={"region": "华东"}, headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(c["region"] == "华东" for c in data["items"])

    def test_按区域筛选_华南(self, client):
        """筛选华南区域，应返回 2 个客户"""
        resp = client.get("/customers", params={"region": "华南"}, headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_无效区域返回400(self, client):
        """传入不存在的区域应返回 400"""
        resp = client.get("/customers", params={"region": "西北"}, headers=_AUTH_HEADERS)
        assert resp.status_code == 400
        assert "无效的区域" in resp.json()["detail"]

    def test_分页_skip_limit(self, client):
        """分页参数 skip=2, limit=3 应返回第3~5条"""
        resp = client.get("/customers", params={"skip": 2, "limit": 3}, headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 3

    def test_分页_超出总数(self, client):
        """skip 超出总数时应返回空列表"""
        resp = client.get("/customers", params={"skip": 100, "limit": 10}, headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 0

    def test_limit_为0返回422(self, client):
        """limit=0 违反 ge=1 约束，应返回 422"""
        resp = client.get("/customers", params={"limit": 0}, headers=_AUTH_HEADERS)
        assert resp.status_code == 422

    def test_skip_为负数返回422(self, client):
        """skip=-1 违反 ge=0 约束，应返回 422"""
        resp = client.get("/customers", params={"skip": -1}, headers=_AUTH_HEADERS)
        assert resp.status_code == 422

    def test_limit_超过100返回422(self, client):
        """limit=101 超过上限，应返回 422"""
        resp = client.get("/customers", params={"limit": 101}, headers=_AUTH_HEADERS)
        assert resp.status_code == 422


# ============================================================
# /sales/by-region 区域销售统计接口测试
# ============================================================


class TestGetSalesByRegion:
    """区域销售额统计接口测试集"""

    def test_全量统计(self, client):
        """不带日期参数时应返回所有区域的汇总数据"""
        resp = client.get("/sales/by-region", headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        regions = {item["region"] for item in data}
        assert regions == {"华东", "华南", "华北", "西南"}

    def test_华东区域金额正确(self, client):
        """华东区域包含客户1和客户5，订单总额应为 120500"""
        resp = client.get("/sales/by-region", headers=_AUTH_HEADERS)
        data = resp.json()
        huadong = next(item for item in data if item["region"] == "华东")
        # 客户1: 50000 + 12000 = 62000; 客户5: 50000 + 8500 = 58500; 合计 120500
        assert huadong["total_amount"] == pytest.approx(120500.0)
        assert huadong["order_count"] == 4

    def test_日期范围过滤(self, client):
        """限定 2025-06-01 ~ 2025-06-30，应只包含 6 月的订单"""
        resp = client.get(
            "/sales/by-region",
            params={"start_date": "2025-06-01", "end_date": "2025-06-30"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        # 6月订单: 105(华北,8500)；订单107实际为7月，不在范围内
        total = sum(item["total_amount"] for item in data)
        assert total == pytest.approx(8500.0)

    def test_仅起始日期(self, client):
        """只传 start_date 应过滤掉该日期之前的订单"""
        resp = client.get(
            "/sales/by-region",
            params={"start_date": "2025-09-01"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        # 9月起订单: 110(华东,8500), 111(华南,28000), 112(华南,12000)；订单109为8月
        total = sum(item["total_amount"] for item in data)
        assert total == pytest.approx(48500.0)

    def test_日期格式错误返回400(self, client):
        """日期格式不合法应返回 400"""
        resp = client.get(
            "/sales/by-region",
            params={"start_date": "2025/01/01"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 400
        assert "格式错误" in resp.json()["detail"]

    def test_起始晚于结束返回400(self, client):
        """start_date > end_date 应返回 400"""
        resp = client.get(
            "/sales/by-region",
            params={"start_date": "2025-12-01", "end_date": "2025-01-01"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 400
        assert "不能晚于" in resp.json()["detail"]

    def test_无匹配订单返回空列表(self, client):
        """日期范围 outside 所有订单时应返回空列表"""
        resp = client.get(
            "/sales/by-region",
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================
# /customers/{customer_id}/orders 单客户订单查询测试
# ============================================================


class TestGetCustomerOrders:
    """单客户订单查询接口测试集"""

    def test_查询客户1的订单(self, client):
        """客户1应有 2 笔订单"""
        resp = client.get("/customers/1/orders", headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(o["customer_id"] == 1 for o in data)

    def test_订单金额正确(self, client):
        """客户1的订单金额应为 50000 和 12000"""
        resp = client.get("/customers/1/orders", headers=_AUTH_HEADERS)
        data = resp.json()
        amounts = sorted(o["amount"] for o in data)
        assert amounts == [12000.0, 50000.0]

    def test_按日期过滤(self, client):
        """限定 2025-03-01 ~ 2025-03-31，客户1应只有 1 笔订单"""
        resp = client.get(
            "/customers/1/orders",
            params={"start_date": "2025-03-01", "end_date": "2025-03-31"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == 102

    def test_不存在的客户返回404(self, client):
        """查询不存在的客户应返回 404"""
        resp = client.get("/customers/999/orders", headers=_AUTH_HEADERS)
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_customer_id_为字符串返回422(self, client):
        """customer_id 传入非整数应返回 422"""
        resp = client.get("/customers/abc/orders", headers=_AUTH_HEADERS)
        assert resp.status_code == 422

    def test_日期格式错误返回400(self, client):
        """日期格式不合法应返回 400"""
        resp = client.get(
            "/customers/1/orders",
            params={"start_date": "not-a-date"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 400

    def test_无匹配日期返回空列表(self, client):
        """日期范围无匹配订单时应返回空列表"""
        resp = client.get(
            "/customers/1/orders",
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_客户2订单包含正确产品(self, client):
        """客户2的订单应包含 服务器A型 和 防火墙C型"""
        resp = client.get("/customers/2/orders", headers=_AUTH_HEADERS)
        data = resp.json()
        products = {o["product"] for o in data}
        assert products == {"服务器A型", "防火墙C型"}
