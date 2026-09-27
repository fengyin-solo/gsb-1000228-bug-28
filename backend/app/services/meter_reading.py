"""关口计量读数核算：列表显示、换表保存、校验读取共用的同一份口径。

核算只认两个共同依据：表计编号 + 生效时间。
- 同一计量点位置下的表计按生效时间排段，每段只属于一个表计编号；
- 每段电量 = (截止示数 - 起始示数) × 倍率，倍率每段只乘一次，不重复累计；
- 换表当天在生效时间处截断：旧表按止码结算、新表从起码起算，不跨表相减；
- 换表后计量点的当前示数只取最新表计段，旧表示数不再残留。
"""
from __future__ import annotations

from typing import Any

BASIS_FIELDS = ("表计编号", "生效时间")


def to_reading(value: Any) -> float | None:
    """把输入解析成示数：核算与换表保存用同一个解析，避免口径分叉。"""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_multiplier(value: Any) -> float:
    """倍率只在这里解析一次；缺失或非法按 1 处理，全系统同一口径。"""
    parsed = to_reading(value)
    return parsed if parsed is not None and parsed > 0 else 1.0


def _num(value: float) -> float | int:
    return int(value) if float(value).is_integer() else value


def reconcile_meter(meter: dict[str, Any]) -> dict[str, Any]:
    """单块表计的核算视图：起始/当前示数与核算电量，只认本表计编号自己的示数。"""
    start = to_reading(meter.get("上次示数")) or 0.0
    current = to_reading(meter.get("当前示数"))
    if current is None:
        current = start
    ratio = to_multiplier(meter.get("倍率"))
    energy = round((current - start) * ratio, 2)
    return {
        "表计编号": meter.get("表计编号"),
        "计量点位置": meter.get("计量点位置"),
        "生效时间": meter.get("生效时间"),
        "起始示数": _num(start),
        "当前示数": _num(current),
        "倍率": _num(ratio),
        "核算电量": _num(energy),
    }


def reconcile_point(meters: list[dict[str, Any]], position: str) -> dict[str, Any]:
    """计量点级核算：按生效时间排段后汇总，换表当天分段结算、不跨表相减。"""
    own = [meter for meter in meters if str(meter.get("计量点位置") or "") == position]
    own.sort(key=lambda meter: (str(meter.get("生效时间") or ""), str(meter.get("表计编号") or "")))
    segments = [reconcile_meter(meter) for meter in own]
    total = round(sum(to_reading(segment["核算电量"]) or 0.0 for segment in segments), 2)
    current = segments[-1] if segments else None
    return {
        "计量点位置": position,
        "当前表计编号": current["表计编号"] if current else None,
        "当前示数": current["当前示数"] if current else 0,
        "期间电量": _num(total),
        "段明细": segments,
    }
