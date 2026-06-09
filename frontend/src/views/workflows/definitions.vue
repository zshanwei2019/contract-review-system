<template>
  <div class="workflow-definitions">
    <el-card shadow="hover">
      <template #header><span>流程定义</span></template>
      <el-table v-loading="loading" :data="definitions" stripe border>
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column prop="contract_type" label="适用类型" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { workflowsApi } from '@/api/workflows'

const loading = ref(false)
const definitions = ref<any[]>([])

onMounted(async () => {
  loading.value = true
  try { definitions.value = await workflowsApi.getDefinitions() || [] } catch {} finally { loading.value = false }
})
</script>
