<template>
  <div class="contract-detail" v-loading="loading">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button icon="Back" @click="router.back()">返回</el-button>
            <span class="title">合同详情</span>
            <el-tag :type="contractStatusColors[contract.status as ContractStatus] as any" size="large">
              {{ contractStatusLabels[contract.status as ContractStatus] }}
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
            <el-dropdown trigger="click" @command="handleAgentReview">
              <el-button type="primary" plain icon="Connection">
                多Agent审查 <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="all">全部Agent</el-dropdown-item>
                  <el-dropdown-item command="legal">⚖️ 法务审查</el-dropdown-item>
                  <el-dropdown-item command="finance">💰 财务审查</el-dropdown-item>
                  <el-dropdown-item command="business">📋 业务审查</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button
              v-if="contract.risk_level"
              type="success"
              icon="MagicStick"
              :loading="modificationLoading"
              @click="handleGetModifications"
            >
              AI修改建议
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 基本信息 -->
      <el-descriptions :column="2" border class="info-section">
        <el-descriptions-item label="合同编号">{{ contract.contract_no }}</el-descriptions-item>
        <el-descriptions-item label="合同类型">
          <el-tag size="small">{{ contractTypeLabels[contract.contract_type as ContractType] || contract.contract_type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="甲方">{{ contract.party_a || '-' }}</el-descriptions-item>
        <el-descriptions-item label="乙方">{{ contract.party_b || '-' }}</el-descriptions-item>
        <el-descriptions-item label="合同金额">
          {{ contract.amount ? formatAmount(contract.amount) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="币种">{{ contract.currency || 'CNY' }}</el-descriptions-item>
        <el-descriptions-item label="签订日期">{{ contract.sign_date ? String(contract.sign_date).substring(0, 10) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="生效日期">{{ contract.effective_date ? String(contract.effective_date).substring(0, 10) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ contract.expiry_date ? String(contract.expiry_date).substring(0, 10) : '-' }}</el-descriptions-item>
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
            <el-statistic title="审查时间" :value="contract.reviewed_at ? formatDate(contract.reviewed_at) as any : '-'" />
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
          :title="'风险等级: ' + getRiskLabel(aiResult.risk_level)"
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

    <!-- 修改建议对话框 -->
    <el-dialog
      v-model="showModificationDialog"
      title="AI修改建议"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-if="modificationSuggestions.length === 0" style="text-align: center; padding: 40px;">
        <el-empty description="暂无修改建议" />
      </div>
      <div v-else>
        <el-alert
          :title="`共 ${modificationSuggestions.length} 个修改建议`"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        />
        <el-table
          :data="modificationSuggestions"
          border
          style="width: 100%"
          @selection-change="(val: any[]) => selectedSuggestions = val.map((v: any) => v.id)"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column label="条款" prop="clause" width="120" />
          <el-table-column label="优先级" width="100">
            <template #default="{ row }">
              <el-tag :type="getPriorityType(row.priority)">
                {{ getPriorityLabel(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="修改理由" prop="reason" min-width="200" show-overflow-tooltip />
          <el-table-column label="法律依据" prop="legal_basis" min-width="150" show-overflow-tooltip />
        </el-table>
        <div style="margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 4px;">
          <p style="margin: 0 0 8px; font-weight: 600;">📝 详细修改建议：</p>
          <div v-for="item in modificationSuggestions" :key="item.id" style="margin-bottom: 12px;">
            <p style="margin: 0 0 4px; color: #409eff; font-weight: 500;">{{ item.clause }}：</p>
            <p style="margin: 0 0 4px; color: #666;">{{ item.reason }}</p>
            <p style="margin: 0; color: #e6a23c;">⚠️ {{ item.risk_if_not_modified }}</p>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showModificationDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="applyingModifications"
          :disabled="selectedSuggestions.length === 0"
          @click="handleApplyModifications"
        >
          应用选中的修改建议 ({{ selectedSuggestions.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'
import { reviewsApi } from '@/api/reviews'
import { agentApi } from '@/api/agent'
import { contractTypeLabels, contractStatusLabels, contractStatusColors } from '@/types/contract'
import type { ContractType, ContractStatus } from '@/types/contract'
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
const modificationSuggestions = ref<any[]>([])
const showModificationDialog = ref(false)
const selectedSuggestions = ref<string[]>([])
const applyingModifications = ref(false)
const modificationLoading = ref(false)

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
    reviews.value = (reviewsRes as any).items || []
    versions.value = (versionsRes as any) || []
  } catch {
    ElMessage.error('获取合同详情失败')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  await ElMessageBox.confirm('确定提交该合同审查？', '提示', { type: 'warning' })
  try {
    await contractsApi.submit(contractId.value as any)
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
    const result: any = await contractsApi.aiReview(contractId.value)
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

const handleAgentReview = async (command: string) => {
  const agents = command === 'all' ? undefined : [command]
  const label = command === 'all' ? '全部Agent' : { legal: '法务', finance: '财务', business: '业务' }[command]
  
  try {
    await ElMessageBox.confirm(
      `将使用${label}Agent对合同进行协作审查，是否继续？`,
      '多Agent审查',
      { confirmButtonText: '开始', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  
  aiReviewing.value = true
  try {
    const result: any = await agentApi.multiAgentReview(contractId.value, agents)
    aiResult.value = {
      review_task_id: result.review_task_id,
      risk_level: result.merged_result?.risk_level,
      risk_score: result.merged_result?.risk_score,
      summary: result.merged_result?.summary,
      findings_count: result.merged_result?.total_findings,
    }
    showAiResult.value = true
    ElMessage.success('多Agent审查完成')
    fetchContract()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '多Agent审查失败')
  } finally {
    aiReviewing.value = false
  }
}

const handleGetModifications = async () => {
  modificationLoading.value = true
  try {
    const result: any = await contractsApi.getModificationSuggestions(contractId.value)
    modificationSuggestions.value = result.suggestions || []
    showModificationDialog.value = true
    selectedSuggestions.value = []
    if (modificationSuggestions.value.length === 0) {
      ElMessage.info('暂无修改建议，请先完成AI审查')
    }
  } catch (err: any) {
    console.error('获取修改建议失败:', err)
    ElMessage.error(err?.response?.data?.detail || err?.message || '获取修改建议失败，请稍后重试')
  } finally {
    modificationLoading.value = false
  }
}

const handleApplyModifications = async () => {
  if (selectedSuggestions.value.length === 0) {
    ElMessage.warning('请选择要应用的修改建议')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要应用选中的 ${selectedSuggestions.value.length} 个修改建议吗？`,
      '确认修改',
      { confirmButtonText: '应用', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  
  applyingModifications.value = true
  try {
    const result: any = await contractsApi.applyModifications(contractId.value, selectedSuggestions.value)
    ElMessage.success(result.message)
    showModificationDialog.value = false
    fetchContract()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '应用修改建议失败')
  } finally {
    applyingModifications.value = false
  }
}

const getPriorityType = (priority: string) => {
  const map: Record<string, string> = {
    critical: 'danger',
    high: 'warning',
    medium: 'info',
    low: 'success'
  }
  return (map[priority] || 'info') as any
}

const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = {
    critical: '必须修改',
    high: '强烈建议',
    medium: '建议修改',
    low: '可选修改'
  }
  return map[priority] || priority
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
