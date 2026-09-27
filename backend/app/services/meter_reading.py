"""关口计量共用核算：列表显示、换表保存、校验读取都调用这里的同一份结果。

核算口径（三处共用，不再各自判断）：
- 共同依据是表计编号 + 生效时间：同一计量点位置下先按表计编号分段，段内按生效时间排序；
- 示数差只在同一表计编号内部相减：换表当天旧表止码与新表起码生效时间相同，
  但分属两个表计编号，各算各的，不会跨表相减；
- 倍率只在汇总段电量时乘一次：示数记录存原始表码，不提前乘倍率，避免重复计算；
- 上次示数、当前示数取自当前表计（生效时间最新的记录所在段），旧表示数不再残留到展示口径。
"""
from __future__ import annotations

from typing import Any


def to_number(value: Any) -> float | None:
    """把接口入参里的数字字符串转成 float；转不了就返回 None，由调用方决定怎么处理。"""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def reconcile_readings(point: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """按共用口径核算一个计量点位置的示数记录。

    入参 records 是该计量点位置下的全部示数记录（可横跨多次换表），
    返回的结果同时供列表显示、换表保存回显、校验读取使用。
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    ordered: list[dict[str, Any]] = []
    for record in records:
        reading = to_number(record.get("示数"))
        moment = str(record.get("生效时间") or "").strip()
        meter_no = str(record.get("表计编号") or "").strip()
        if reading is None or not moment or not meter_no:
            continue
        normalized = {**record, "表计编号": meter_no, "生效时间": moment, "示数": reading}
        groups.setdefault(meter_no, []).append(normalized)
        ordered.append(normalized)

    segments: list[dict[str, Any]] = []
    total = 0.0
    for meter_no, rows in groups.items():
        rows.sort(key=lambda row: row["生效时间"])
        if len(rows) < 2:
            continue
        first, last = rows[0], rows[-1]
        ratio = to_number(last.get("倍率")) or to_number(first.get("倍率")) or 1.0
        energy = round((last["示数"] - first["示数"]) * ratio, 2)
        total += energy
        segments.append({
            "表计编号": meter_no,
            "起始时间": first["生效时间"],
            "终止时间": last["生效时间"],
            "起始示数": first["示数"],
            "终止示数": last["示数"],
            "倍率": ratio,
            "段电量": energy,
        })

    active_no: str | None = None
    active_moment = ""
    for record in ordered:
        # 生效时间相同时后写入的记录优先：换表当天新表起码排在旧表止码之后，当前表计就是新表
        if record["生效时间"] >= active_moment:
            active_no = record["表计编号"]
            active_moment = record["生效时间"]

    previous: float | None = None
    current: float | None = None
    current_moment: str | None = None
    if active_no is not None:
        active_rows = groups[active_no]
        current = active_rows[-1]["示数"]
        current_moment = active_rows[-1]["生效时间"]
        if len(active_rows) > 1:
            previous = active_rows[-2]["示数"]

    return {
        "计量点位置": point,
        "当前表计编号": active_no,
        "上次示数": previous,
        "当前示数": current,
        "生效时间": current_moment,
        "区间电量": round(total, 2),
        "分段明细": segments,
    }
