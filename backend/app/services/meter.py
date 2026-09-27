"""关口计量业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.services.meter_reading import reconcile_readings, to_number
from app.store import store

MODULE = "meter"
REQUIRED_FIELDS = ["表计编号", "表计型号", "计量点位置"]
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
        # 列表显示走共用核算：上次/当前示数与区间电量和换表保存、校验读取看到的一致
        return [self._with_reconciliation(row) for row in rows[start:start + size]], total

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
        entry["示数记录"] = []
        entry["换表记录"] = []
        rows.append(entry)
        return entry, []

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

    def save_replacement(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """换表保存：写入旧表止码与新表起码两条示数记录，再按共用口径重算并回显。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"计量表计 {entry_id} 不存在或已归档"
        old_no = str(entry.get("表计编号") or "").strip()
        new_no = str(values.get("新表计编号") or "").strip()
        moment = str(values.get("生效时间") or "").strip()
        if not new_no:
            return None, "换表保存缺少新表计编号"
        if new_no == old_no:
            return None, f"新表计编号与在运表计「{old_no}」相同，请核对后再保存"
        if not moment:
            return None, "换表保存缺少生效时间"
        new_start = to_number(values.get("新表起码"))
        if new_start is None or new_start < 0:
            return None, "新表起码需要是不小于 0 的数字"

        current = self._reconcile(entry)
        old_final = to_number(values.get("旧表止码"))
        if old_final is None:
            old_final = current["当前示数"]
        if old_final is None:
            return None, "旧表还没有示数记录，请补录旧表止码"
        if current["当前示数"] is not None and old_final < current["当前示数"]:
            return None, f"旧表止码 {old_final} 小于最近示数 {current['当前示数']}，请核对"
        if current["生效时间"] and moment < current["生效时间"]:
            return None, f"生效时间早于旧表最近示数时间 {current['生效时间']}，请核对换表日期"

        old_ratio = to_number(entry.get("倍率")) or 1.0
        raw_ratio = to_number(values.get("新表倍率"))
        if raw_ratio is None:
            new_ratio = old_ratio
        elif raw_ratio <= 0:
            return None, "新表倍率需要是大于 0 的数字"
        else:
            new_ratio = raw_ratio

        records = list(entry.get("示数记录") or [])
        closing = {"表计编号": old_no, "生效时间": moment, "示数": old_final, "倍率": old_ratio, "来源": "换表"}
        opening = {"表计编号": new_no, "生效时间": moment, "示数": new_start, "倍率": new_ratio, "来源": "换表"}
        entry["示数记录"] = [*records, closing, opening]
        history = list(entry.get("换表记录") or [])
        history.append({"旧表计编号": old_no, "新表计编号": new_no, "生效时间": moment, "旧表止码": old_final, "新表起码": new_start})
        entry["换表记录"] = history
        entry["表计编号"] = new_no
        entry["倍率"] = new_ratio
        new_model = str(values.get("新表型号") or "").strip()
        if new_model:
            entry["表计型号"] = new_model
        merged = self._with_reconciliation(entry, detail=True)
        return merged, f"换表已保存：{old_no} → {new_no}，列表与校验读取将看到同一份核算结果"

    def read_calibration(self, entry_id: int) -> dict[str, Any] | None:
        """校验入口读取：与列表显示、换表保存共用同一份核算结果。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._reconcile(entry)

    def _reconcile(self, entry: dict[str, Any]) -> dict[str, Any]:
        """共用核算：列表显示、换表保存、校验读取都拿这一份结果。"""
        records = list(entry.get("示数记录") or [])
        return reconcile_readings(str(entry.get("计量点位置") or ""), records)

    def _with_reconciliation(self, entry: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
        merged = dict(entry)
        result = self._reconcile(entry)
        merged["上次示数"] = result["上次示数"]
        merged["当前示数"] = result["当前示数"]
        merged["区间电量"] = result["区间电量"]
        if detail:
            merged["核算结果"] = result
        return merged
