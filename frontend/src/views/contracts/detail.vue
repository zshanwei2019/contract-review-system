<template>
  <div class="contract-detail" v-loading="loading">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button icon="Back" @click="router.back()">返回</el-button>
            <span class="title">合同详情</span>
            <el-tag :type="contractStatusColors[contract.status]" size="large">
              {{ contractStatusLabels[contract.status] }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button
              v-if="contract.status === 'draft'"
              type="success"
              icon="Check"
              @click="handleSubmit"
            >
              提交审查
            </el-button>
            <el-button
              v-if="canReview"
              type="primary"
              icon="Search"
              @click="handleReview"
            >
              开始审查
            </el-button>
            <el-button
              type="warning"
              icon="MagicStick"
              :loading="aiReviewing"
              @click="handleAiReview"
            >
              AI智能审查
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 基本信息 -->
      <el-descriptions :column="2" border class="info-section">
        <el-descriptions-item label="合同编号">{{ contract.contract_no }}</el-descriptions-item>
        <el-descriptions-item label="合同类型">
          <el-tag size="small">{{ contractTypeLabels[contract.contract_type] }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="甲方">{{ contract.party_a || '-' }}</el-descriptions-item>
        <el-descriptions-item label="乙方">{{ contract.party_b || '-' }}</el-descriptions-item>
        <el-descriptions-item label="合同金额">
          {{ contract.amount ? formatAmount(contract.amount) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="币种">{{ contract.currency || 'CNY' }}</el-descriptions-item>
        <el-descriptions-item label="签订日期">{{ contract.sign_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="生效日期">{{ contract.effective_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ contract.expiry_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="所属部门">{{ contract.department || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目名称" :span="2">{{ contract.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="合同描述" :span="2">{{ contract.description || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <!-- 风险信息 -->
      <div v-if="contract.risk_level" class="risk-section">
        <h3>风险评估</h3>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-statistic title="风险等级">
              <template #default>
                <el-tag :type="getRiskColor(contract.risk_level)" size="large">
                  {{ getRiskLabel(contract.risk_level) }}
                </el-tag>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="风险评分" :value="contract.risk_score || 0" suffix="/ 100" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="审查时间" :value="contract.reviewed_at ? formatDate(contract.reviewed_at) : '-'" />
          </el-col>
        </el-row>
      </div>
      
      <!-- 审查记录 -->
      <div class="review-section">
        <h3>审查记录</h3>
        <el-timeline v-if="reviews.length > 0">
          <el-timeline-item
            v-for="review in reviews"
            :key="review.id"
            :timestamp="formatDate(review.created_at)"
            placement="top"
          >
            <el-card shadow="never">
              <div class="review-item">
                <div class="review-header">
                  <el-tag :type="getReviewStatusColor(review.status)" size="small">
                    {{ reviewStatusLabels[review.status] }}
                  </el-tag>
                  <span class="reviewer">审查人：{{ review.reviewer?.name || '-' }}</span>
                </div>
                <p v-if="review.summary" class="review-summary">{{ review.summary }}</p>
                <el-button text type="primary" @click="router.push(`/reviews/${review.id}`)">
                  查看详情
                </el-button>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无审查记录" />
      </div>
      
      <!-- 版本历史 -->
      <div class="version-section">
        <h3>版本历史</h3>
        <el-table v-if="versions.length > 0" :data="versions" border>
          <el-table-column prop="version_no" label="版本号" width="100" />
          <el-table-column prop="description" label="变更说明" min-width="200" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无版本记录" />
      </div>
    </el-card>
    
    <!-- AI审查结果对话框 -->
    <el-dialog v-model="showAiResult" title="AI智能审查结果" width="700px">
      <div v-if="aiResult.risk_level">
        <el-alert
          :title="`风险等级: ${getRiskLabel(aiResult.risk_level)}`
          :description="aiResult.summary"
          :type="aiResult.risk_level === 'high' ? 'error' : aiResult.risk_level === 'medium' ? 'warning' : 'success'"
          show-icon
          :closable="false"
          style="margin-bottom: 20px"
        />
        
        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="12">
            <el-statistic title="风险评分" :value="aiResult.risk_score" suffix="/ 100" />
          </el-col>
          <el-col :span="12">
            <el-statistic title="发现项数" :value="aiResult.findings_count" suffix="项" />
          </el-col>
        </el-row>
        
        <p style="color: #666; margin: 0;">
          审查意见已自动生成，可在「审查记录」中查看详细内容。
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="router.push(`/reviews/${aiResult.review_task_id}`)">
          查看审查详情
        </el-button>
        <el-button @click="showAiResult = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'
import { reviewsApi } from '@/api/reviews'
import { contractTypeLabels, contractStatusLabels, contractStatusColors } from '@/types/contract'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const aiReviewing = ref(false)
const contract = ref<any>({})
const reviews = ref<any[]>([])
const versions = ref<any[]>([])
const showAiResult = ref(false)
const aiResult = ref<any>({})

const contractId = computed(() => Number(route.params.id))

const canReview = computed(() => {
  return ['pending_review', 'reviewing'].includes(contract.value.status)
})

const fetchContract = async () => {
  loading.value = true
  try {
    contract.value = await contractsApi.get(contractId.value)
    const [reviewsRes, versionsRes] = await Promise.all([
      reviewsApi.list({ contract_id: contractId.value }),
      contractsApi.getVersions(contractId.value),
    ])
    reviews.value = reviewsRes.items || []
    versions.value = versionsRes || []
  } catch {
    ElMessage.error('获取合同详情失败')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  await ElMessageBox.confirm('确定提交该合同审查？', '提示', { type: 'warning' })
  try {
    await contractsApi.submit(contractId.value)
    ElMessage.success('提交成功')
    fetchContract()
  } catch {
    ElMessage.error('提交失败')
  }
}

const handleReview = () => {
  router.push(`/reviews/list?contract_id=${contractId.value}`)
}

const handleAiReview = async () => {
  try {
    await ElMessageBox.confirm(
      'AI将对合同进行智能风险审查，是否继续？',
      'AI智能审查',
      { confirmButtonText: '开始审查', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  
  aiReviewing.value = true
  try {
    const result = await contractsApi.aiReview(contractId.value)
    aiResult.value = result
    showAiResult.value = true
    ElMessage.success('AI审查完成')
    fetchContract()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI审查失败，请稍后重试')
  } finally {
    aiReviewing.value = false
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

const getReviewStatusColor = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'danger',
  }
  return (map[status] || 'info') as any
}

const reviewStatusLabels: Record<string, string> = {
  pending: '待处理',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm')

onMounted(() => {
  fetchContract()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.info-section {
  margin-bottom: 24px;
}

.risk-section,
.review-section,
.version-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

.risk-section h3,
.review-section h3,
.version-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
}

.review-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.reviewer {
  color: #666;
  font-size: 14px;
}

.review-summary {
  margin: 0;
  color: #333;
}
</style>
