<template>
  <div class="risk-items">
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>风险项列表</span>
          <el-button type="success" icon="Refresh" @click="handleInitItems" :loading="initLoading">初始化风险项</el-button>
        </div>
      </template>
      
      <div class="search-bar">
        <el-select v-model="searchForm.risk_level" placeholder="风险等级" clearable style="width: 150px">
          <el-option label="高风险" value="high" />
          <el-option label="中风险" value="medium" />
          <el-option label="低风险" value="low" />
        </el-select>
        <el-select v-model="searchForm.is_resolved" placeholder="处理状态" clearable style="width: 150px">
          <el-option label="未处理" :value="false" />
          <el-option label="已处理" :value="true" />
        </el-select>
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
      </div>
      
      <el-table v-loading="loading" :data="items" stripe border>
        <el-table-column prop="title" label="风险标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getRiskColor(row.risk_level)" size="small">
              {{ getRiskLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="clause_location" label="条款位置" width="150" show-overflow-tooltip />
        <el-table-column prop="clause_text" label="涉及条款" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.clause_text" class="clause-text">{{ row.clause_text }}</span>
            <span v-else class="no-clause">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="{ row }">
            <el-progress
              v-if="row.confidence"
              :percentage="Math.round(row.confidence * 100)"
              :stroke-width="10"
              :color="getConfidenceColor(row.confidence)"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="contract.title" label="关联合同" width="200" show-overflow-tooltip />
        <el-table-column prop="is_resolved" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_resolved ? 'success' : 'warning'" size="small">
              {{ row.is_resolved ? '已处理' : '未处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.is_resolved"
              text
              type="success"
              size="small"
              @click="handleResolve(row)"
            >
              标记处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          layout="total, prev, pager, next"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { risksApi } from '@/api/risks'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const loading = ref(false)
const initLoading = ref(false)
const items = ref<any[]>([])
const searchForm = reactive({ risk_level: '', is_resolved: undefined as boolean | undefined })
const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const getRiskColor = (level: string) => {
  const map: Record<string, string> = { high: 'danger', medium: 'warning', low: 'success' }
  return (map[level] || 'info') as any
}

const getRiskLabel = (level: string) => {
  const map: Record<string, string> = { high: '高风险', medium: '中风险', low: '低风险' }
  return map[level] || level
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm')

const fetchItems = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (searchForm.risk_level) params.risk_level = searchForm.risk_level
    if (searchForm.is_resolved !== undefined) params.is_resolved = searchForm.is_resolved
    
    const res: any = await risksApi.getItems(params)
    items.value = res.items || []
    pagination.total = res.total || 0
  } catch { ElMessage.error('获取风险项失败') } finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchItems() }

const handleResolve = async (row: any) => {
  await ElMessageBox.confirm('确定标记该风险项为已处理？', '提示')
  try {
    await risksApi.updateItem(row.id, { is_resolved: true })
    ElMessage.success('已标记处理')
    fetchItems()
  } catch { ElMessage.error('操作失败') }
}

const handleInitItems = async () => {
  try {
    initLoading.value = true
    const res: any = await risksApi.initItems()
    ElMessage.success(res.message || '初始化成功')
    await fetchItems()
  } catch { ElMessage.error('初始化失败') } finally { initLoading.value = false }
}

onMounted(() => { fetchItems() })
</script>

<style scoped>
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.clause-text {
  font-family: monospace;
  font-size: 12px;
  color: #606266;
  background-color: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.no-clause {
  color: #c0c4cc;
}
</style>
