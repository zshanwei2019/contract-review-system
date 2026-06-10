<template>
  <div class="contract-list">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>合同列表</span>
          <el-button type="primary" icon="Plus" @click="router.push('/contracts/create')">
            新建合同
          </el-button>
        </div>
      </template>
      
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-input
          v-model="searchForm.keyword"
          placeholder="搜索合同名称、编号、甲乙方"
          prefix-icon="Search"
          clearable
          style="width: 300px"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="searchForm.contract_type" placeholder="合同类型" clearable style="width: 150px">
          <el-option
            v-for="(label, value) in contractTypeLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
        <el-select v-model="searchForm.status" placeholder="状态" clearable style="width: 150px">
          <el-option
            v-for="(label, value) in contractStatusLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
        <el-button icon="Refresh" @click="handleReset">重置</el-button>
      </div>
      
      <!-- 表格 -->
      <el-table
        v-loading="loading"
        :data="contracts"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column prop="contract_no" label="合同编号" width="160" />
        <el-table-column prop="title" label="合同名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="contract_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ (contractTypeLabels as any)[row.contract_type] || row.contract_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="(contractStatusColors as any)[row.status]" size="small">
              {{ (contractStatusLabels as any)[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="party_a" label="甲方" width="150" show-overflow-tooltip />
        <el-table-column prop="party_b" label="乙方" width="150" show-overflow-tooltip />
        <el-table-column prop="amount" label="金额(元)" width="120" align="right">
          <template #default="{ row }">
            {{ row.amount ? formatAmount(row.amount) : '-' }}
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
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/contracts/${row.id}`)">
              查看
            </el-button>
            <el-button
              v-if="row.status === 'draft'"
              text
              type="success"
              size="small"
              @click="handleSubmit(row)"
            >
              提交
            </el-button>
            <el-button
              v-if="row.status === 'draft'"
              text
              type="danger"
              size="small"
              @click="handleDelete(row)"
            >
              删除
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
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'
import { contractTypeLabels, contractStatusLabels, contractStatusColors } from '@/types/contract'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const contracts = ref<any[]>([])

const searchForm = reactive({
  keyword: '',
  contract_type: '',
  status: '',
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const fetchContracts = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.contract_type) params.contract_type = searchForm.contract_type
    if (searchForm.status) params.status = searchForm.status
    
    const res: any = await contractsApi.list(params)
    contracts.value = res.items || []
    pagination.total = res.total || 0
  } catch {
    ElMessage.error('获取合同列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchContracts()
}

const handleReset = () => {
  searchForm.keyword = ''
  searchForm.contract_type = ''
  searchForm.status = ''
  handleSearch()
}

const handleSubmit = async (row: any) => {
  await ElMessageBox.confirm('确定提交该合同审查？', '提示', { type: 'warning' })
  try {
    await contractsApi.submit(row.id)
    ElMessage.success('提交成功')
    fetchContracts()
  } catch {
    ElMessage.error('提交失败')
  }
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm('确定删除该合同？此操作不可撤销', '警告', { type: 'error' })
  try {
    await contractsApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchContracts()
  } catch {
    ElMessage.error('删除失败')
  }
}

const formatAmount = (amount: number) => {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(amount)
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

onMounted(() => {
  fetchContracts()
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
  flex-wrap: wrap;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
