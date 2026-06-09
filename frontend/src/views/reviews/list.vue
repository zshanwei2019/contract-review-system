<template>
  <div class="review-list">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>审查列表</span>
        </div>
      </template>
      
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-select v-model="searchForm.status" placeholder="状态" clearable style="width: 150px">
          <el-option label="待处理" value="pending" />
          <el-option label="进行中" value="in_progress" />
          <el-option label="已完成" value="completed" />
        </el-select>
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
        <el-button icon="Refresh" @click="handleReset">重置</el-button>
      </div>
      
      <!-- 表格 -->
      <el-table v-loading="loading" :data="reviews" stripe border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="contract.title" label="合同名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusColor(row.status)" size="small">
              {{ statusLabels[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.risk_level" :type="getRiskColor(row.risk_level)" size="small">
              {{ getRiskLabel(row.risk_level) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="风险评分" width="100" align="center">
          <template #default="{ row }">
            {{ row.risk_score || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="deadline" label="截止时间" width="180">
          <template #default="{ row }">
            {{ row.deadline ? formatDate(row.deadline) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/reviews/${row.id}`)">
              查看
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              text
              type="success"
              size="small"
              @click="handleStart(row)"
            >
              开始
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { reviewsApi } from '@/api/reviews'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const reviews = ref<any[]>([])

const searchForm = reactive({
  status: '',
  contract_id: route.query.contract_id ? Number(route.query.contract_id) : undefined,
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const statusLabels: Record<string, string> = {
  pending: '待处理',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

const getStatusColor = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'danger',
  }
  return (map[status] || 'info') as any
}

const getRiskColor = (level: string) => {
  const map: Record<string, string> = { high: 'danger', medium: 'warning', low: 'success' }
  return (map[level] || 'info') as any
}

const getRiskLabel = (level: string) => {
  const map: Record<string, string> = { high: '高风险', medium: '中风险', low: '低风险' }
  return map[level] || level
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm')

const fetchReviews = async () => {
  loading.value = true
  try {
    const res = await reviewsApi.list({
      page: pagination.page,
      page_size: pagination.page_size,
      ...searchForm,
    })
    reviews.value = res.items || []
    pagination.total = res.total || 0
  } catch {
    ElMessage.error('获取审查列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchReviews()
}

const handleReset = () => {
  searchForm.status = ''
  searchForm.contract_id = undefined
  handleSearch()
}

const handleStart = async (row: any) => {
  try {
    await reviewsApi.update(row.id, { status: 'in_progress' })
    ElMessage.success('已开始审查')
    fetchReviews()
  } catch {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  fetchReviews()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
