<template>
  <div class="notifications">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>消息通知</span>
          <div>
            <el-select v-model="filterType" placeholder="全部类型" clearable size="small" style="width: 120px; margin-right: 8px" @change="loadNotifications">
              <el-option label="审查分配" value="review_assigned" />
              <el-option label="审查完成" value="review_completed" />
              <el-option label="合同提交" value="contract_submitted" />
              <el-option label="工作流" value="workflow" />
              <el-option label="系统" value="system" />
            </el-select>
            <el-button text @click="handleMarkAllRead" :disabled="!hasUnread">全部已读</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="notifications" stripe>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTagColor(row.type)">{{ typeLabels[row.type] || row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'unread' ? 'warning' : 'info'" size="small">
              {{ row.status === 'unread' ? '未读' : '已读' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'unread'" link type="primary" @click="handleMarkRead(row)">已读</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="loadNotifications"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { notificationsApi } from '@/api/notifications'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const loading = ref(false)
const notifications = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const filterType = ref('')

const typeLabels: Record<string, string> = {
  review_assigned: '审查分配',
  review_completed: '审查完成',
  contract_submitted: '合同提交',
  workflow: '工作流',
  system: '系统',
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
function typeTagColor(type: string): TagType {
  return ({ review_assigned: 'warning', review_completed: 'success', contract_submitted: 'primary', workflow: 'info', system: 'info' } as const)[type] || 'info'
}

const hasUnread = computed(() => notifications.value.some(n => n.status === 'unread'))

const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

async function loadNotifications() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: 20 }
    if (filterType.value) params.type = filterType.value
    const res: any = await notificationsApi.list(params)
    notifications.value = res.items || res.data || []
    total.value = res.total || 0
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleMarkRead(row: any) {
  try {
    await notificationsApi.markRead(row.id)
    loadNotifications()
  } catch {}
}

async function handleMarkAllRead() {
  try {
    await notificationsApi.markAllRead()
    ElMessage.success('已全部标记已读')
    loadNotifications()
  } catch {}
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm('确认删除此通知？', '提示')
  try {
    await notificationsApi.delete(row.id)
    ElMessage.success('已删除')
    loadNotifications()
  } catch {}
}

onMounted(() => { loadNotifications() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
