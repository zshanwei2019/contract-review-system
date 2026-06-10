<template>
  <div class="workflow-instances">
    <el-card shadow="hover">
      <template #header><span>流程实例</span></template>
      <el-table v-loading="loading" :data="instances" stripe border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="contract.title" label="合同" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusColor(row.status)" size="small">{{ statusLabels[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="当前步骤" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { workflowsApi } from '@/api/workflows'
import dayjs from 'dayjs'

const loading = ref(false)
const instances = ref<any[]>([])
const statusLabels: Record<string, string> = { running: '运行中', completed: '已完成', rejected: '已驳回', cancelled: '已取消' }
const getStatusColor = (s: string) => ({ running: 'primary', completed: 'success', rejected: 'danger', cancelled: 'info' }[s] || 'info') as any
const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

onMounted(async () => {
  loading.value = true
  try { instances.value = (await workflowsApi.getDefinitions() as any) || [] } catch {} finally { loading.value = false }
})
</script>
