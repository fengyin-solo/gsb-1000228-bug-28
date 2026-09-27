<template>
  <section class="page" data-module="meter">
    <header class="page-head">
      <div>
        <h2>关口计量管理</h2>
        <p class="page-desc">维护计量表计，围绕表计编号、表计型号、计量点位置、倍率做登记、筛选与状态流转；换表后的读数核算由列表、换表、校验读取共用同一口径。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记计量表计</button>
        <button class="btn" type="button" @click="exportRows">导出关口计量清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openReplace(row)">换表</button>
            <button class="link" type="button" @click="openCalibration(row)">校验读取</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无关口计量数据，可先登记计量表计</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条关口计量记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="replaceTarget" class="dialog-mask" @click.self="closeReplace">
      <div class="dialog">
        <template v-if="!replaceResult">
          <h3>换表登记 · {{ replaceTarget['计量点位置'] }}</h3>
          <p class="dialog-desc">
            在运表计 {{ replaceTarget['表计编号'] }}（倍率 {{ replaceTarget['倍率'] ?? '—' }}）。
            保存后按表计编号 + 生效时间分段核算，与列表、校验读取看到的结果一致。
          </p>
          <form class="dialog-form" @submit.prevent="submitReplace">
            <label><span>新表计编号 *</span><input v-model.trim="replaceForm.新表计编号" placeholder="如 METE-0005" /></label>
            <label><span>新表型号</span><input v-model.trim="replaceForm.新表型号" placeholder="缺省沿用原型号" /></label>
            <label><span>新表倍率</span><input v-model.trim="replaceForm.新表倍率" placeholder="缺省沿用在运倍率" /></label>
            <label><span>新表起码 *</span><input v-model.trim="replaceForm.新表起码" placeholder="新表起始示数" /></label>
            <label><span>旧表止码</span><input v-model.trim="replaceForm.旧表止码" placeholder="缺省取旧表最近示数" /></label>
            <label><span>生效时间 *</span><input v-model="replaceForm.生效时间" type="date" /></label>
            <p v-if="replaceError" class="error-text form-error">{{ replaceError }}</p>
            <div class="dialog-actions">
              <button class="btn ghost" type="button" @click="closeReplace">取消</button>
              <button class="btn primary" type="submit" :disabled="replaceSaving">{{ replaceSaving ? '保存中…' : '保存换表' }}</button>
            </div>
          </form>
        </template>
        <template v-else>
          <h3>换表已保存 · {{ replaceResult['计量点位置'] }}</h3>
          <p class="dialog-desc">以下为共用核算结果，列表刷新后与校验读取看到的完全一致。</p>
          <div class="result-grid">
            <div><span>当前表计编号</span><strong>{{ replaceResult.当前表计编号 ?? '—' }}</strong></div>
            <div><span>上次示数</span><strong>{{ replaceResult.上次示数 ?? '—' }}</strong></div>
            <div><span>当前示数</span><strong>{{ replaceResult.当前示数 ?? '—' }}</strong></div>
            <div><span>生效时间</span><strong>{{ replaceResult.生效时间 ?? '—' }}</strong></div>
            <div><span>区间电量</span><strong>{{ replaceResult.区间电量 }}</strong></div>
          </div>
          <div class="dialog-actions">
            <button class="btn primary" type="button" @click="closeReplace">完成</button>
          </div>
        </template>
      </div>
    </div>

    <div v-if="calibrationTarget" class="dialog-mask" @click.self="closeCalibration">
      <div class="dialog">
        <h3>校验读取 · {{ calibrationTarget['计量点位置'] }}</h3>
        <p class="dialog-desc">校验入口读取的共用核算结果，与列表显示、换表保存一致。</p>
        <p v-if="calibrationError" class="error-text">{{ calibrationError }}</p>
        <template v-if="calibration">
          <div class="result-grid">
            <div><span>当前表计编号</span><strong>{{ calibration.当前表计编号 ?? '—' }}</strong></div>
            <div><span>上次示数</span><strong>{{ calibration.上次示数 ?? '—' }}</strong></div>
            <div><span>当前示数</span><strong>{{ calibration.当前示数 ?? '—' }}</strong></div>
            <div><span>生效时间</span><strong>{{ calibration.生效时间 ?? '—' }}</strong></div>
            <div><span>区间电量</span><strong>{{ calibration.区间电量 }}</strong></div>
          </div>
          <table v-if="calibration.分段明细.length" class="data-table">
            <thead>
              <tr><th>表计编号</th><th>起始时间</th><th>终止时间</th><th>起始示数</th><th>终止示数</th><th>倍率</th><th>段电量</th></tr>
            </thead>
            <tbody>
              <tr v-for="segment in calibration.分段明细" :key="segment.表计编号">
                <td>{{ segment.表计编号 }}</td>
                <td>{{ segment.起始时间 }}</td>
                <td>{{ segment.终止时间 }}</td>
                <td>{{ segment.起始示数 }}</td>
                <td>{{ segment.终止示数 }}</td>
                <td>{{ segment.倍率 }}</td>
                <td>{{ segment.段电量 }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div class="dialog-actions">
          <button class="btn primary" type="button" @click="closeCalibration">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

type Segment = {
  表计编号: string
  起始时间: string
  终止时间: string
  起始示数: number
  终止示数: number
  倍率: number
  段电量: number
}

type ReconcileResult = {
  计量点位置: string
  当前表计编号: string | null
  上次示数: number | null
  当前示数: number | null
  生效时间: string | null
  区间电量: number
  分段明细: Segment[]
}

const ENDPOINT = '/api/meter'
const columns = ["表计编号", "表计型号", "计量点位置", "倍率", "上次示数", "当前示数", "区间电量", "校验日期", "表计状态"]
const actions = ["记录示数", "标记异常", "送检校验"]
const statuses = ["正常运行", "通讯中断", "示数异常", "待校验"]
const stats = [{"label": "正常表计", "value": 0}, {"label": "异常表计", "value": 0}, {"label": "待校验表计", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const replaceTarget = ref<Row | null>(null)
const replaceForm = ref({ 新表计编号: '', 新表型号: '', 新表倍率: '', 新表起码: '', 旧表止码: '', 生效时间: '' })
const replaceError = ref('')
const replaceSaving = ref(false)
const replaceResult = ref<ReconcileResult | null>(null)

const calibrationTarget = ref<Row | null>(null)
const calibration = ref<ReconcileResult | null>(null)
const calibrationError = ref('')

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '计量表计登记入口尚未接入审批流'
}

function openReplace(row: Row) {
  replaceTarget.value = row
  replaceForm.value = {
    新表计编号: '',
    新表型号: '',
    新表倍率: String(row['倍率'] ?? ''),
    新表起码: '',
    旧表止码: '',
    生效时间: new Date().toISOString().slice(0, 10),
  }
  replaceError.value = ''
  replaceResult.value = null
}

function closeReplace() {
  replaceTarget.value = null
  replaceResult.value = null
  replaceError.value = ''
}

async function submitReplace() {
  if (!replaceTarget.value || replaceSaving.value) {
    return
  }
  replaceError.value = ''
  replaceSaving.value = true
  try {
    const response = await request(`${ENDPOINT}/${replaceTarget.value.id}/replacement`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...replaceForm.value } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '换表保存失败，请核对后重试')
    }
    replaceResult.value = (payload.entry?.核算结果 ?? null) as ReconcileResult | null
    await reload()
  } catch (error) {
    replaceError.value = error instanceof Error ? error.message : '换表保存失败'
  } finally {
    replaceSaving.value = false
  }
}

async function openCalibration(row: Row) {
  calibrationTarget.value = row
  calibration.value = null
  calibrationError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/calibration`)
    if (!response.ok) {
      throw new Error('校验读取失败，请稍后重试')
    }
    calibration.value = (await response.json()) as ReconcileResult
  } catch (error) {
    calibrationError.value = error instanceof Error ? error.message : '校验读取失败'
  }
}

function closeCalibration() {
  calibrationTarget.value = null
  calibration.value = null
  calibrationError.value = ''
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '关口计量动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '关口计量操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('计量表计列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '关口计量列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.dialog {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 560px;
  max-width: 92vw;
  max-height: 86vh;
  overflow: auto;
}
.dialog h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.dialog-desc {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
}
.dialog-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}
.dialog-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.dialog-form input {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.form-error {
  grid-column: 1 / -1;
  margin: 0;
}
.dialog-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.result-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 10px 0 14px;
}
.result-grid div {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
  color: var(--muted);
}
.result-grid strong {
  display: block;
  color: #1f2937;
  font-size: 15px;
  margin-top: 2px;
}
</style>
