<template>
  <div class="integration-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-card shadow="never"><el-statistic title="集成总数" :value="stats.total || 0" /></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><el-statistic title="活跃集成" :value="stats.active || 0" /></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><el-statistic title="今日同步" :value="stats.today_syncs || 0" /></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><el-statistic title="今日Webhook" :value="stats.today_webhooks || 0" /></el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 集成配置 -->
      <el-tab-pane label="集成配置" name="configs">
        <div class="search-bar">
          <el-select v-model="filterType" placeholder="系统类型" clearable style="width: 140px" @change="loadConfigs">
            <el-option label="OA" value="oa" />
            <el-option label="ERP" value="erp" />
            <el-option label="CRM" value="crm" />
            <el-option label="SAP" value="sap" />
            <el-option label="其他" value="other" />
          </el-select>
          <el-button type="success" @click="showCreate = true">添加集成</el-button>
        </div>

        <el-table :data="configs" v-loading="loading" stripe style="margin-top: 16px">
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column prop="system_type" label="类型" width="80">
            <template #default="{ row }">
              <el-tag size="small">{{ systemTypeLabel(row.system_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="api_url" label="API地址" min-width="250" show-overflow-tooltip />
          <el-table-column prop="auth_type" label="认证" width="80" />
          <el-table-column prop="sync_direction" label="同步方向" width="100" />
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_sync_at" label="最后同步" width="170">
            <template #default="{ row }">{{ formatTime(row.last_sync_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="handleTest(row.id)">测试</el-button>
              <el-button link type="success" @click="handleSync(row.id)">同步</el-button>
              <el-button link @click="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Webhook 事件 -->
      <el-tab-pane label="Webhook事件" name="webhooks">
        <el-table :data="webhooks" v-loading="webhookLoading" stripe>
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="120" />
          <el-table-column prop="event_type" label="事件类型" width="180" />
          <el-table-column prop="event_id" label="事件ID" width="200" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'processed' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="retry_count" label="重试" width="60" align="right" />
        </el-table>
      </el-tab-pane>

      <!-- 同步日志 -->
      <el-tab-pane label="同步日志" name="synclogs">
        <el-table :data="syncLogs" v-loading="logLoading" stripe>
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="direction" label="方向" width="80" />
          <el-table-column prop="entity_type" label="实体" width="100" />
          <el-table-column prop="entity_id" label="实体ID" width="120" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="records_count" label="记录数" width="80" align="right" />
          <el-table-column prop="duration_ms" label="耗时(ms)" width="100" align="right" />
          <el-table-column prop="error_message" label="错误" min-width="200" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加/编辑集成弹窗 -->
    <el-dialog v-model="showCreate" :title="editingId ? '编辑集成' : '添加集成'" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="系统类型" required>
          <el-select v-model="form.system_type" style="width: 100%">
            <el-option label="OA" value="oa" />
            <el-option label="ERP" value="erp" />
            <el-option label="CRM" value="crm" />
            <el-option label="SAP" value="sap" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="API地址"><el-input v-model="form.api_url" placeholder="https://..." /></el-form-item>
        <el-form-item label="API Key"><el-input v-model="form.api_key" show-password /></el-form-item>
        <el-form-item label="API Secret"><el-input v-model="form.api_secret" show-password /></el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="form.auth_type" style="width: 100%">
            <el-option label="Bearer Token" value="bearer" />
            <el-option label="Basic Auth" value="basic" />
            <el-option label="API Key" value="api_key" />
            <el-option label="OAuth2" value="oauth2" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用同步">
          <el-switch v-model="form.sync_enabled" />
        </el-form-item>
        <el-form-item label="同步间隔(秒)"><el-input-number v-model="form.sync_interval" :min="60" :step="60" /></el-form-item>
        <el-form-item label="同步方向">
          <el-radio-group v-model="form.sync_direction">
            <el-radio value="inbound">仅入站</el-radio>
            <el-radio value="outbound">仅出站</el-radio>
            <el-radio value="bidirectional">双向</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleSave">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { integrationApi } from '@/api/integration'

const activeTab = ref('configs')
const loading = ref(false)
const configs = ref<any[]>([])
const stats = ref<any>({})
const filterType = ref('')

const webhookLoading = ref(false)
const webhooks = ref<any[]>([])
const logLoading = ref(false)
const syncLogs = ref<any[]>([])

const showCreate = ref(false)
const editingId = ref(0)
const form = reactive<any>({
  name: '', system_type: 'oa', api_url: '', api_key: '', api_secret: '',
  auth_type: 'bearer', sync_enabled: false, sync_interval: 300, sync_direction: 'bidirectional',
})

function formatTime(val: string) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}
function systemTypeLabel(s: string) {
  return { oa: 'OA', erp: 'ERP', crm: 'CRM', sap: 'SAP', other: '其他' }[s] || s
}

async function loadStats() {
  try { const res = await integrationApi.stats(); stats.value = res.data || {} } catch {}
}

async function loadConfigs() {
  loading.value = true
  try {
    const params: any = {}
    if (filterType.value) params.system_type = filterType.value
    const res = await integrationApi.listConfigs(params)
    configs.value = res.data || []
  } catch (e: any) { ElMessage.error(e.message || '加载失败') }
  finally { loading.value = false }
}

async function loadWebhooks() {
  webhookLoading.value = true
  try { const res = await integrationApi.listWebhooks({ page: 1, size: 50 }); webhooks.value = res.data || [] }
  catch (e: any) { ElMessage.error(e.message) } finally { webhookLoading.value = false }
}

async function loadSyncLogs() {
  logLoading.value = true
  try { const res = await integrationApi.listSyncLogs({ page: 1, size: 50 }); syncLogs.value = res.data || [] }
  catch (e: any) { ElMessage.error(e.message) } finally { logLoading.value = false }
}

function handleEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name, system_type: row.system_type, api_url: row.api_url || '',
    api_key: '', api_secret: '', auth_type: row.auth_type,
    sync_enabled: row.sync_enabled, sync_interval: row.sync_interval, sync_direction: row.sync_direction,
  })
  showCreate.value = true
}

async function handleSave() {
  try {
    if (editingId.value) {
      await integrationApi.updateConfig(editingId.value, form)
      ElMessage.success('已更新')
    } else {
      await integrationApi.createConfig(form)
      ElMessage.success('已添加')
    }
    showCreate.value = false
    editingId.value = 0
    loadConfigs()
    loadStats()
  } catch (e: any) { ElMessage.error(e.message || '保存失败') }
}

async function handleTest(id: number) {
  try {
    const res = await integrationApi.testConnection(id)
    if (res.data.success) ElMessage.success(res.data.message)
    else ElMessage.warning(res.data.message)
  } catch (e: any) { ElMessage.error(e.message) }
}

async function handleSync(id: number) {
  try {
    await integrationApi.triggerSync(id)
    ElMessage.success('同步完成')
    loadConfigs()
    loadStats()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确认删除此集成配置？', '提示')
  try {
    await integrationApi.deleteConfig(id)
    ElMessage.success('已删除')
    loadConfigs()
    loadStats()
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(() => {
  loadStats()
  loadConfigs()
  loadWebhooks()
  loadSyncLogs()
})
</script>

<style scoped>
.search-bar { display: flex; gap: 12px; align-items: center; }
</style>
