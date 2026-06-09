<template>
  <div class="notifications">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>消息通知</span>
          <el-button text @click="handleMarkAllRead">全部已读</el-button>
        </div>
      </template>
      
      <el-table v-loading="loading" :data="notifications" stripe>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabels[row.type] || row.type }}</el-tag>
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
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="row.status === 'unread'" text type="primary" size="small" @click="handleMarkRead(row)">已读</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { notificationsApi } from '@/api/notifications'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

const loading = ref(false)
const notifications = ref<any[]>([])
const typeLabels: Record<string, string> = { review_assigned: '审查分配', review_completed: '审查完成', contract_submitted: '合同提交', workflow: '工作流', system: '系统' }
const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

const fetchNotifications = async () => {
  loading.value = true
  try { const res = await notificationsApi.list({}); notifications.value = res.items || [] } catch {} finally { loading.value = false }
}

const handleMarkRead = async (row: any) => {
  try { await notificationsApi.markRead(row.id); fetchNotifications() } catch {}
}

const handleMarkAllRead = async () => {
  try { await notificationsApi.markAllRead(); ElMessage.success('已全部标记已读'); fetchNotifications() } catch {}
}

const handleDelete = async (row: any) => {
  try { await notificationsApi.delete(row.id); fetchNotifications() } catch {}
}

onMounted(() => { fetchNotifications() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
