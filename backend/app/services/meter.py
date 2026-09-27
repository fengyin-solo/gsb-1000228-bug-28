"""关口计量业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.meter_reading import reconcile_meter, reconcile_point, to_reading
from app.store import store

MODULE = "meter"
REPLACE_MODULE = "meter_replace"
REQUIRED_FIELDS = ["表计编号", "表计型号", "计量点位置"]
REPLACE_REQUIRED_FIELDS = ["新表编号", "新表起码", "生效时间"]
STATUS_ORDER = ["正常运行", "通讯中断", "示数异常", "待校验"]
ACTION_RULES = {"记录示数": "正常运行", "标记异常": "示数异常", "送检校验": "待校验"}
NEGATIVE_ACTIONS = []


class MeterService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("表计编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        # 列表显示：每行挂共用核算结果，不在路由或前端另算
        return [self._with_reconcile(row) for row in rows[start:start + size]], total

    def _with_reconcile(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item.update(reconcile_meter(row))
        return item

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def replace_meter(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """换表保存：旧表止码取自共用核算，新表自生效时间起算，当天不跨表相减。"""
        old = store.find(MODULE, entry_id)
        if old is None:
            return None, f"计量表计 {entry_id} 不存在或已归档"
        if old.get("换表去向"):
            return None, f"表计 {old.get('表计编号')} 已换给 {old['换表去向']}，不能重复换表"
        missing = [field for field in REPLACE_REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        new_code = str(values["新表编号"]).strip()
        if any(str(row.get("表计编号")) == new_code for row in store.rows(MODULE)):
            return None, f"表计编号 {new_code} 已存在，换表不能复用旧编号"
        start_reading = to_reading(values["新表起码"])
        if start_reading is None:
            return None, "新表起码需要是数字，请核对后再保存"
        effective = str(values["生效时间"]).strip()
        try:
            datetime.strptime(effective, "%Y-%m-%d")
        except ValueError:
            return None, "生效时间需要是 YYYY-MM-DD 格式"
        old_effective = str(old.get("生效时间") or "")
        if old_effective and effective < old_effective:
            return None, f"生效时间不能早于旧表生效时间 {old_effective}"
        # 旧表止码与列表、校验读取同一份核算结果，冻结后旧表示数不再残留
        stop_reading = reconcile_meter(old)["当前示数"]
        old["当前示数"] = stop_reading
        old["换表去向"] = new_code
        replace_rows = store.rows(REPLACE_MODULE)
        replace_rows.append({
            "id": max((int(row.get("id", 0)) for row in replace_rows), default=0) + 1,
            "计量点位置": old.get("计量点位置"),
            "旧表编号": old.get("表计编号"),
            "新表编号": new_code,
            "旧表止码": stop_reading,
            "新表起码": start_reading,
            "生效时间": effective,
        })
        rows = store.rows(MODULE)
        new_meter: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "表计编号": new_code,
            "表计型号": str(values.get("表计型号") or old.get("表计型号") or "").strip(),
            "计量点位置": old.get("计量点位置"),
            "倍率": values.get("倍率") or old.get("倍率"),
            "上次示数": start_reading,
            "当前示数": start_reading,
            "生效时间": effective,
            "校验日期": values.get("校验日期") or old.get("校验日期"),
            "表计状态": STATUS_ORDER[0],
            "换表来源": old.get("表计编号"),
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
        }
        rows.append(new_meter)
        message = f"已换表：{old.get('表计编号')} 止码 {stop_reading}，{new_code} 自 {effective} 起从起码 {start_reading} 核算"
        return self._with_reconcile(new_meter), message

    def check_entry(self, entry_id: int) -> dict[str, Any] | None:
        """校验读取：与列表显示、换表保存共用同一份核算结果。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        code = entry.get("表计编号")
        return {
            "表计核算": reconcile_meter(entry),
            "计量点核算": reconcile_point(store.rows(MODULE), str(entry.get("计量点位置") or "")),
            "换表记录": [
                row for row in store.rows(REPLACE_MODULE)
                if code in (row.get("旧表编号"), row.get("新表编号"))
            ],
        }

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"计量表计 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于关口计量可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"计量表计已{action}"
