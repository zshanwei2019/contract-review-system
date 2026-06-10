<template>
  <div class="review-detail" v-loading="loading">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button icon="Back" @click="router.back()">返回</el-button>
            <span class="title">审查详情</span>
            <el-tag :type="getStatusColor(review.status)" size="large">
              {{ statusLabels[review.status] }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button
              v-if="review.status === 'pending'"
              type="success"
              icon="VideoPlay"
              @click="handleStart"
            >
              开始审查
            </el-button>
            <el-button
              v-if="review.status === 'in_progress'"
              type="primary"
              icon="Check"
              @click="showCompleteDialog = true"
            >
              完成审查
            </el-button>
            <el-button
              v-if="review.status === 'completed'"
              type="warning"
              icon="Star"
              @click="showRatingDialog = true"
            >
              评价审查
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 审查信息 -->
      <el-descriptions :column="2" border>
        <el-descriptions-item label="合同名称">
          <el-button text type="primary" @click="router.push(`/contracts/${review.contract_id}`)">
            {{ review.contract?.title || '-' }}
          </el-button>
        </el-descriptions-item>
        <el-descriptions-item label="合同类型">
          {{ (contractTypeLabels as any)[review.contract?.contract_type] || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="风险等级">
          <el-tag v-if="review.risk_level" :type="getRiskColor(review.risk_level)">
            {{ getRiskLabel(review.risk_level) }}
          </el-tag>
          <span v-else>待评估</span>
        </el-descriptions-item>
        <el-descriptions-item label="风险评分">
          {{ review.risk_score || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="截止时间">
          {{ review.deadline ? formatDate(review.deadline) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="完成时间">
          {{ review.completed_at ? formatDate(review.completed_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="审查摘要" :span="2">
          {{ review.summary || '-' }}
        </el-descriptions-item>
      </el-descriptions>
      
      <!-- 审查意见 -->
      <div class="opinions-section">
        <div class="section-header">
          <h3>审查意见</h3>
          <el-button
            v-if="review.status === 'in_progress'"
            type="primary"
            icon="Plus"
            @click="showOpinionDialog = true"
          >
            添加意见
          </el-button>
        </div>
        
        <el-timeline v-if="opinions.length > 0">
          <el-timeline-item
            v-for="opinion in opinions"
            :key="opinion.id"
            :timestamp="formatDate(opinion.created_at)"
            placement="top"
            :type="getOpinionColor(opinion.opinion_type)"
          >
            <el-card shadow="never">
              <div class="opinion-item">
                <div class="opinion-header">
                  <el-tag :type="getOpinionColor(opinion.opinion_type)" size="small">
                    {{ opinionTypeLabels[opinion.opinion_type] }}
                  </el-tag>
                  <el-tag v-if="opinion.risk_level" :type="getRiskColor(opinion.risk_level)" size="small">
                    {{ getRiskLabel(opinion.risk_level) }}
                  </el-tag>
                </div>
                <p class="opinion-content">{{ opinion.content }}</p>
                <p v-if="opinion.suggestion" class="opinion-suggestion">
                  <strong>建议：</strong>{{ opinion.suggestion }}
                </p>
                <div v-if="opinion.clause_reference || opinion.legal_basis" class="opinion-meta">
                  <span v-if="opinion.clause_reference">条款引用：{{ opinion.clause_reference }}</span>
                  <span v-if="opinion.legal_basis">法律依据：{{ opinion.legal_basis }}</span>
                </div>
                <el-button
                  text
                  type="warning"
                  size="small"
                  @click="openCorrection(opinion)"
                  style="margin-top: 8px"
                >
                  📝 提交修正
                </el-button>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无审查意见" />
      </div>
    </el-card>
    
    <!-- 添加意见对话框 -->
    <el-dialog v-model="showOpinionDialog" title="添加审查意见" width="600px">
      <el-form :model="opinionForm" label-width="100px">
        <el-form-item label="意见类型" required>
          <el-select v-model="opinionForm.opinion_type" style="width: 100%">
            <el-option label="风险提示" value="risk" />
            <el-option label="改进建议" value="suggestion" />
            <el-option label="修改意见" value="modification" />
            <el-option label="审批意见" value="approval" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级" v-if="opinionForm.opinion_type === 'risk'">
          <el-select v-model="opinionForm.risk_level" style="width: 100%">
            <el-option label="高风险" value="high" />
            <el-option label="中风险" value="medium" />
            <el-option label="低风险" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="意见内容" required>
          <el-input v-model="opinionForm.content" type="textarea" :rows="4" placeholder="请输入意见内容" />
        </el-form-item>
        <el-form-item label="改进建议">
          <el-input v-model="opinionForm.suggestion" type="textarea" :rows="3" placeholder="请输入改进建议" />
        </el-form-item>
        <el-form-item label="条款引用">
          <el-input v-model="opinionForm.clause_reference" placeholder="如：第三条第二款" />
        </el-form-item>
        <el-form-item label="法律依据">
          <el-input v-model="opinionForm.legal_basis" placeholder="如：《民法典》第XXX条" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showOpinionDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAddOpinion">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 完成审查对话框 -->
    <el-dialog v-model="showCompleteDialog" title="完成审查" width="500px">
      <el-form :model="completeForm" label-width="100px">
        <el-form-item label="风险等级" required>
          <el-select v-model="completeForm.risk_level" style="width: 100%">
            <el-option label="高风险" value="high" />
            <el-option label="中风险" value="medium" />
            <el-option label="低风险" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险评分">
          <el-slider v-model="completeForm.risk_score" :max="100" show-input />
        </el-form-item>
        <el-form-item label="审查总结">
          <el-input v-model="completeForm.summary" type="textarea" :rows="4" placeholder="请输入审查总结" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCompleteDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleComplete">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 评价审查对话框 -->
    <el-dialog v-model="showRatingDialog" title="评价审查质量" width="500px">
      <el-form :model="ratingForm" label-width="100px">
        <el-form-item label="评分">
          <el-rate v-model="ratingForm.rating" :max="5" show-score />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="ratingForm.comment" type="textarea" :rows="3" placeholder="请输入评语（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRatingDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRating">提交评价</el-button>
      </template>
    </el-dialog>
    
    <!-- 修正意见对话框 -->
    <el-dialog v-model="showCorrectionDialog" title="提交修正意见" width="600px">
      <el-form :model="correctionForm" label-width="100px">
        <el-form-item label="原始意见">
          <el-input :model-value="selectedOpinion?.content" type="textarea" :rows="3" disabled />
        </el-form-item>
        <el-form-item label="修正类型">
          <el-select v-model="correctionForm.correction_type" style="width: 100%">
            <el-option label="修改内容" value="modify" />
            <el-option label="删除该意见" value="delete" />
            <el-option label="补充新增" value="add" />
          </el-select>
        </el-form-item>
        <el-form-item label="修正内容" required>
          <el-input v-model="correctionForm.corrected_opinion" type="textarea" :rows="4" placeholder="请输入修正后的意见" />
        </el-form-item>
        <el-form-item label="修正原因" required>
          <el-input v-model="correctionForm.correction_reason" type="textarea" :rows="3" placeholder="请说明修正原因，帮助AI学习改进" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCorrectionDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCorrection">提交修正</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reviewsApi } from '@/api/reviews'
import { agentApi } from '@/api/agent'
import { contractTypeLabels } from '@/types/contract'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const review = ref<any>({})
const opinions = ref<any[]>([])
const showOpinionDialog = ref(false)
const showCompleteDialog = ref(false)
const showRatingDialog = ref(false)
const showCorrectionDialog = ref(false)
const selectedOpinion = ref<any>(null)

const reviewId = computed(() => Number(route.params.id))

const opinionForm = reactive({
  opinion_type: 'risk',
  content: '',
  suggestion: '',
  risk_level: '',
  clause_reference: '',
  legal_basis: '',
})

const completeForm = reactive({
  risk_level: '',
  risk_score: 50,
  summary: '',
})

const ratingForm = reactive({
  rating: 4,
  comment: '',
})

const correctionForm = reactive({
  corrected_opinion: '',
  correction_reason: '',
  correction_type: 'modify',
})

const statusLabels: Record<string, string> = {
  pending: '待处理',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

const opinionTypeLabels: Record<string, string> = {
  risk: '风险提示',
  suggestion: '改进建议',
  modification: '修改意见',
  approval: '审批意见',
}

const getStatusColor = (status: string) => {
  const map: Record<string, string> = { pending: 'info', in_progress: 'warning', completed: 'success', cancelled: 'danger' }
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

const getOpinionColor = (type: string) => {
  const map: Record<string, string> = { risk: 'danger', suggestion: 'primary', modification: 'warning', approval: 'success' }
  return (map[type] || 'info') as any
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm')

const fetchReview = async () => {
  loading.value = true
  try {
    review.value = await reviewsApi.get(reviewId.value)
    const opinionsRes: any = await reviewsApi.getOpinions(reviewId.value)
    opinions.value = opinionsRes || []
  } catch {
    ElMessage.error('获取审查详情失败')
  } finally {
    loading.value = false
  }
}

const handleStart = async () => {
  try {
    await reviewsApi.update(reviewId.value, { status: 'in_progress' })
    ElMessage.success('已开始审查')
    fetchReview()
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleAddOpinion = async () => {
  if (!opinionForm.content) {
    ElMessage.warning('请输入意见内容')
    return
  }
  submitting.value = true
  try {
    await reviewsApi.createOpinion(reviewId.value, opinionForm)
    ElMessage.success('意见已添加')
    showOpinionDialog.value = false
    opinionForm.content = ''
    opinionForm.suggestion = ''
    fetchReview()
  } catch {
    ElMessage.error('添加失败')
  } finally {
    submitting.value = false
  }
}

const handleComplete = async () => {
  if (!completeForm.risk_level) {
    ElMessage.warning('请选择风险等级')
    return
  }
  submitting.value = true
  try {
    await reviewsApi.update(reviewId.value, {
      status: 'completed',
      risk_level: completeForm.risk_level,
      risk_score: completeForm.risk_score,
      summary: completeForm.summary,
    })
    ElMessage.success('审查已完成')
    showCompleteDialog.value = false
    fetchReview()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleRating = async () => {
  try {
    // 先获取案例ID（从审查任务关联）
    await agentApi.rateCase(review.value.id, ratingForm.rating, ratingForm.comment)
    ElMessage.success('评价已提交，感谢反馈！')
    showRatingDialog.value = false
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '评价失败')
  }
}

const openCorrection = (opinion: any) => {
  selectedOpinion.value = opinion
  correctionForm.corrected_opinion = opinion.content
  correctionForm.correction_reason = ''
  showCorrectionDialog.value = true
}

const handleCorrection = async () => {
  if (!correctionForm.correction_reason) {
    ElMessage.warning('请填写修正原因')
    return
  }
  try {
    await agentApi.submitCorrection({
      review_case_id: reviewId.value,
      original_opinion_id: selectedOpinion.value?.id,
      corrected_opinion: correctionForm.corrected_opinion,
      correction_reason: correctionForm.correction_reason,
      correction_type: correctionForm.correction_type,
    })
    ElMessage.success('修正已提交，系统将学习此反馈')
    showCorrectionDialog.value = false
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '提交失败')
  }
}

onMounted(() => {
  fetchReview()
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

.opinions-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.opinion-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.opinion-header {
  display: flex;
  gap: 8px;
}

.opinion-content {
  margin: 0;
  color: #333;
}

.opinion-suggestion {
  margin: 0;
  color: #666;
}

.opinion-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #999;
}
</style>
