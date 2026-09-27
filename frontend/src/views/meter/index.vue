<template>
  <section class="page" data-module="meter">
    <header class="page-head">
      <div>
        <h2>关口计量管理</h2>
        <p class="page-desc">维护计量表计，围绕表计编号、计量点位置做登记、换表与状态流转；读数核算统一走同一份口径。</p>
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
            <button class="link" type="button" @click="openCheck(row)">校验读取</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无关口计量数据，可先登记计量表计</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条关口计量记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="replaceVisible" class="modal-mask" @click.self="closeReplace">
      <div class="modal">
        <header class="modal-head">
          <h3 class="modal-title">换表登记：{{ replaceTarget?.表计编号 }}（{{ replaceTarget?.计量点位置 }}）</h3>
          <button class="link" type="button" @click="closeReplace">关闭</button>
        </header>
        <p class="modal-tip">
          旧表止码 <strong>{{ replaceStopReading ?? '—' }}</strong>（取自共用核算，与列表、校验读取同一口径），
          新表自生效时间起算，换表当天分段结算、不跨表相减。
        </p>
        <div class="form-grid">
          <label class="form-item">
            <span>新表编号 *</span>
            <input v-model="replaceForm.新表编号" placeholder="如 METE-0005" />
          </label>
          <label class="form-item">
            <span>新表型号</span>
            <input v-model="replaceForm.新表型号" placeholder="默认同旧表" />
          </label>
          <label class="form-item">
            <span>新表起码 *</span>
            <input v-model="replaceForm.新表起码" placeholder="新表起始示数" />
          </label>
          <label class="form-item">
            <span>倍率</span>
            <input v-model="replaceForm.倍率" placeholder="默认同旧表" />
          </label>
          <label class="form-item">
            <span>生效时间 *</span>
            <input v-model="replaceForm.生效时间" type="date" />
          </label>
        </div>
        <p v-if="replaceError" class="error-text">{{ replaceError }}</p>
        <footer class="modal-actions">
          <button class="btn ghost" type="button" @click="closeReplace">取消</button>
          <button class="btn primary" type="button" :disabled="saving" @click="submitReplace">
            {{ saving ? '保存中…' : '保存换表' }}
          </button>
        </footer>
      </div>
    </div>

    <div v-if="checkResult" class="modal-mask" @click.self="checkResult = null">
      <div class="modal">
        <header class="modal-head">
          <h3 class="modal-title">校验读取：{{ checkResult.表计核算.表计编号 }}</h3>
          <button class="link" type="button" @click="checkResult = null">关闭</button>
        </header>
        <section class="modal-section">
          <h4>表计核算（与列表、换表保存同一份结果）</h4>
          <dl class="kv-list">
            <template v-for="key in meterKeys" :key="key">
              <dt>{{ key }}</dt>
              <dd>{{ checkResult.表计核算[key] ?? '—' }}</dd>
            </template>
          </dl>
        </section>
        <section class="modal-section">
          <h4>计量点核算：{{ checkResult.计量点核算.计量点位置 }}（当前表计 {{ checkResult.计量点核算.当前表计编号 }}，期间电量 {{ checkResult.计量点核算.期间电量 }}）</h4>
          <table class="data-table">
            <thead>
              <tr><th v-for="key in segmentKeys" :key="key">{{ key }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(segment, index) in checkResult.计量点核算.段明细" :key="index">
                <td v-for="key in segmentKeys" :key="key">{{ segment[key] ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
        <section v-if="checkResult.换表记录.length" class="modal-section">
          <h4>换表记录</h4>
          <table class="data-table">
            <thead>
              <tr><th v-for="key in replaceKeys" :key="key">{{ key }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="record in checkResult.换表记录" :key="String(record.id)">
                <td v-for="key in replaceKeys" :key="key">{{ record[key] ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Segment = Record<string, string | number | null>
interface CheckResult {
  表计核算: Segment
  计量点核算: Segment & { 段明细: Segment[] }
  换表记录: Segment[]
}

const ENDPOINT = '/api/meter'
const columns = ["表计编号", "表计型号", "计量点位置", "倍率", "上次示数", "当前示数", "生效时间", "核算电量", "校验日期", "表计状态"]
const actions = ["记录示数", "标记异常", "送检校验"]
const meterKeys = ["表计编号", "计量点位置", "生效时间", "起始示数", "当前示数", "倍率", "核算电量"]
const segmentKeys = ["表计编号", "生效时间", "起始示数", "当前示数", "倍率", "核算电量"]
const replaceKeys = ["旧表编号", "新表编号", "旧表止码", "新表起码", "生效时间"]
const stats = [{"label": "正常表计", "value": 0}, {"label": "异常表计", "value": 0}, {"label": "待校验表计", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const replaceVisible = ref(false)
const replaceTarget = ref<Row | null>(null)
const replaceStopReading = ref<string | number | null>(null)
const replaceForm = ref({ 新表编号: '', 新表型号: '', 新表起码: '', 倍率: '', 生效时间: '' })
const replaceError = ref('')
const saving = ref(false)
const checkResult = ref<CheckResult | null>(null)

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

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('关口计量动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '关口计量操作失败'
  }
}

async function openReplace(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  replaceTarget.value = row
  replaceForm.value = {
    新表编号: '',
    新表型号: '',
    新表起码: '',
    倍率: String(row.倍率 ?? ''),
    生效时间: new Date().toISOString().slice(0, 10),
  }
  replaceError.value = ''
  replaceStopReading.value = null
  replaceVisible.value = true
  try {
    // 弹窗里的旧表止码也走校验读取的同一份核算，不另起口径
    const response = await request(`${ENDPOINT}/${row.id}/check`)
    if (response.ok) {
      const result = (await response.json()) as CheckResult
      replaceStopReading.value = result.表计核算.当前示数 ?? null
    }
  } catch {
    replaceStopReading.value = null
  }
}

function closeReplace() {
  replaceVisible.value = false
  replaceTarget.value = null
}

async function submitReplace() {
  if (!replaceTarget.value) {
    return
  }
  saving.value = true
  replaceError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${replaceTarget.value.id}/replace`, {
      method: 'POST',
      body: JSON.stringify({ values: replaceForm.value }),
    })
    const result = (await response.json()) as { ok: boolean; message: string }
    if (!result.ok) {
      replaceError.value = result.message
      return
    }
    closeReplace()
    noticeMessage.value = result.message
    await reload()
  } catch (error) {
    replaceError.value = error instanceof Error ? error.message : '换表保存失败'
  } finally {
    saving.value = false
  }
}

async function openCheck(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/check`)
    if (!response.ok) {
      throw new Error('校验读取失败，请稍后重试')
    }
    checkResult.value = (await response.json()) as CheckResult
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '校验读取失败'
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
