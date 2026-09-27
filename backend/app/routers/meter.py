"""关口计量接口：维护计量表计，覆盖记录示数、标记异常、送检校验等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.meter import MeterService

router = APIRouter(prefix="/api/meter", tags=["关口计量"])

service = MeterService()

LIST_FIELDS = ["表计编号", "表计型号", "计量点位置", "倍率", "上次示数", "当前示数", "校验日期", "表计状态"]
STATUSES = ["正常运行", "通讯中断", "示数异常", "待校验"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按表计编号检索"),
    status: str | None = Query(default=None, description="正常运行、通讯中断、示数异常、待校验"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按表计编号与状态过滤关口计量列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条计量表计明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"计量表计 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条计量表计，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="计量表计已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条计量表计执行记录示数、标记异常、送检校验；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/replacement", response_model=ActionResult)
def save_replacement(entry_id: int, payload: EntryPayload) -> ActionResult:
    """换表保存：写入旧表止码与新表起码，返回与列表、校验读取一致的共用核算结果。"""
    entry, message = service.save_replacement(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/{entry_id}/calibration", response_model=dict)
def read_calibration(entry_id: int) -> dict:
    """校验入口读取：与列表显示、换表保存共用同一份核算结果。"""
    result = service.read_calibration(entry_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"计量表计 {entry_id} 不存在或已归档")
    return result


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出关口计量清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "meter", "total": total, "items": items}
