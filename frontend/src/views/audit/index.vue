<template>
  <div class="audit-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="近7天操作总数" :value="statsData.total || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="成功操作" :value="statsData.by_status?.success || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="失败操作" :value="statsData.by_status?.failure || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="活跃用户数" :value="Object.keys(statsData.by_user || {}).length" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 审计日志 -->
      <el-tab-pane label="审计日志" name="audit">
        <div class="search-bar">
          <el-input v-model="auditFilter.username" placeholder="用户名" clearable style="width: 140px" @keyup.enter="loadAuditLogs" />
          <el-select v-model="auditFilter.action" placeholder="操作类型" clearable style="width: 140px" @change="loadAuditLogs">
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="登录" value="login" />
            <el-option label="登出" value="logout" />
            <el-option label="提交" value="submit" />
            <el-option label="审批" value="approve" />
            <el-option label="驳回" value="reject" />
          </el-select>
          <el-select v-model="auditFilter.resource_type" placeholder="资源类型" clearable style="width: 140px" @change="loadAuditLogs">
            <el-option label="合同" value="contract" />
            <el-option label="审查" value="review" />
            <el-option label="用户" value="user" />
            <el-option label="工作流" value="workflow" />
            <el-option label="风险" value="risk" />
          </el-select>
          <el-select v-model="auditFilter.status" placeholder="状态" clearable style="width: 100px" @change="loadAuditLogs">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failure" />
          </el-select>
          <el-date-picker v-model="auditFilter.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" @change="loadAuditLogs" />
          <el-button type="primary" @click="loadAuditLogs">搜索</el-button>
        </div>

        <el-table :data="auditLogs" v-loading="auditLoading" stripe style="margin-top: 16px">
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120" />
          <el-table-column prop="action" label="操作" width="100">
            <template #default="{ row }">
              <el-tag :type="actionTagType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="resource_type" label="资源类型" width="100" />
          <el-table-column prop="resource_name" label="资源名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="status" label="结果" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status === 'success' ? '成功' : '失败' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="ip_address" label="IP" width="130" />
          <el-table-column label="详情" width="80">
            <template #default="{ row }">
              <el-button link type="primary" @click="showDetail(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="auditTotal > 0"
          v-model:current-page="auditPage"
          :page-size="20"
          :total="auditTotal"
          layout="total, prev, pager, next"
          style="margin-top: 16px; justify-content: flex-end"
          @current-change="loadAuditLogs"
        />
      </el-tab-pane>

      <!-- 操作日志 -->
      <el-tab-pane label="操作日志" name="operation">
        <div class="search-bar">
          <el-input v-model="opFilter.username" placeholder="用户名" clearable style="width: 140px" @keyup.enter="loadOpLogs" />
          <el-select v-model="opFilter.method" placeholder="HTTP方法" clearable style="width: 100px" @change="loadOpLogs">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
          </el-select>
          <el-date-picker v-model="opFilter.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" @change="loadOpLogs" />
          <el-button type="primary" @click="loadOpLogs">搜索</el-button>
        </div>

        <el-table :data="opLogs" v-loading="opLoading" stripe style="margin-top: 16px">
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120" />
          <el-table-column prop="method" label="方法" width="80">
            <template #default="{ row }">
              <el-tag :type="methodTagType(row.method)" size="small">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="路径" min-width="300" show-overflow-tooltip />
          <el-table-column prop="response_code" label="状态码" width="80">
            <template #default="{ row }">
              <el-tag :type="codeTagType(row.response_code)" size="small">{{ row.response_code }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="耗时(ms)" width="100" align="right" />
          <el-table-column prop="ip_address" label="IP" width="130" />
        </el-table>

        <el-pagination
          v-if="opTotal > 0"
          v-model:current-page="opPage"
          :page-size="20"
          :total="opTotal"
          layout="total, prev, pager, next"
          style="margin-top: 16px; justify-content: flex-end"
          @current-change="loadOpLogs"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="审计日志详情" width="600px">
      <el-descriptions :column="1" border v-if="currentDetail">
        <el-descriptions-item label="时间">{{ formatTime(currentDetail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{ currentDetail.username }}</el-descriptions-item>
        <el-descriptions-item label="操作">{{ actionLabel(currentDetail.action) }}</el-descriptions-item>
        <el-descriptions-item label="资源类型">{{ currentDetail.resource_type }}</el-descriptions-item>
        <el-descriptions-item label="资源名称">{{ currentDetail.resource_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentDetail.status === 'success' ? 'success' : 'danger'" size="small">{{ currentDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentDetail.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="详情">{{ currentDetail.detail }}</el-descriptions-item>
        <el-descriptions-item v-if="currentDetail.error_message" label="错误信息">
          <span style="color: #f56c6c">{{ currentDetail.error_message }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { auditApi } from '@/api/audit'

const activeTab = ref('audit')
const statsData = ref<any>({})

// 审计日志
const auditLoading = ref(false)
const auditLogs = ref<any[]>([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditFilter = reactive<any>({
  username: '',
  action: '',
  resource_type: '',
  status: '',
  dateRange: null,
})

// 操作日志
const opLoading = ref(false)
const opLogs = ref<any[]>([])
const opTotal = ref(0)
const opPage = ref(1)
const opFilter = reactive<any>({
  username: '',
  method: '',
  dateRange: null,
})

// 详情
const detailVisible = ref(false)
const currentDetail = ref<any>(null)

function formatTime(val: string) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

function actionLabel(val: string) {
  const map: Record<string, string> = {
    create: '创建', update: '更新', delete: '删除',
    login: '登录', logout: '登出', submit: '提交',
    approve: '审批', reject: '驳回',
  }
  return map[val] || val
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function actionTagType(val: string): TagType {
  const map: Record<string, TagType> = {
    create: 'success', delete: 'danger', login: 'info',
    approve: 'warning', reject: 'danger',
  }
  return map[val] || 'info'
}

function methodTagType(val: string): TagType {
  const map: Record<string, TagType> = { GET: 'info', POST: 'success', PUT: 'warning', DELETE: 'danger' }
  return map[val] || 'info'
}

function codeTagType(code: number): TagType {
  if (!code) return 'info'
  if (code < 300) return 'success'
  if (code < 400) return 'info'
  if (code < 500) return 'warning'
  return 'danger'
}

async function loadStats() {
  try {
    const res = await auditApi.stats(7)
    statsData.value = res.data || {}
  } catch {}
}

async function loadAuditLogs() {
  auditLoading.value = true
  try {
    const params: any = {
      page: auditPage.value,
      size: 20,
      username: auditFilter.username || undefined,
      action: auditFilter.action || undefined,
      resource_type: auditFilter.resource_type || undefined,
      status: auditFilter.status || undefined,
    }
    if (auditFilter.dateRange && auditFilter.dateRange.length === 2) {
      params.start_date = auditFilter.dateRange[0].toISOString()
      params.end_date = auditFilter.dateRange[1].toISOString()
    }
    const [listRes, countRes] = await Promise.all([
      auditApi.listAuditLogs(params),
      auditApi.countAuditLogs(params),
    ])
    auditLogs.value = listRes.data || []
    auditTotal.value = countRes.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    auditLoading.value = false
  }
}

async function loadOpLogs() {
  opLoading.value = true
  try {
    const params: any = {
      page: opPage.value,
      size: 20,
      username: opFilter.username || undefined,
      method: opFilter.method || undefined,
    }
    if (opFilter.dateRange && opFilter.dateRange.length === 2) {
      params.start_date = opFilter.dateRange[0].toISOString()
      params.end_date = opFilter.dateRange[1].toISOString()
    }
    const res = await auditApi.listOperationLogs(params)
    opLogs.value = res.data || []
    // 操作日志没有单独的 count API，用返回长度估算
    opTotal.value = res.data?.length === 20 ? opPage.value * 20 + 1 : opPage.value * 20
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    opLoading.value = false
  }
}

function showDetail(row: any) {
  currentDetail.value = row
  detailVisible.value = true
}

onMounted(() => {
  loadStats()
  loadAuditLogs()
})
</script>

<style scoped>
.search-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>
