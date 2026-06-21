<template>
  <div class="workflow-instances">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header-flex">
          <span>审批流程实例</span>
          <div>
            <el-select v-model="filterStatus" placeholder="筛选状态" clearable size="small" style="width: 140px; margin-right: 8px" @change="loadData">
              <el-option label="运行中" value="running" />
              <el-option label="已完成" value="completed" />
              <el-option label="已驳回" value="rejected" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="instances" stripe border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="合同" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="goToContract(row.contract_id)">
              合同 #{{ row.contract_id }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusColor(row.status)" size="small">{{ statusLabels[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="当前步骤" width="100" />
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="getProgress(row)"
              :status="row.status === 'completed' ? 'success' : row.status === 'rejected' ? 'exception' : ''"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="initiator_id" label="发起人" width="100">
          <template #default="{ row }">用户#{{ row.initiator_id }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="发起时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 实例详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="审批流程详情" width="700px">
      <div v-if="currentInstance">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border size="small" class="mb-16">
          <el-descriptions-item label="合同ID">{{ currentInstance.contract_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusColor(currentInstance.status)" size="small">{{ statusLabels[currentInstance.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="发起人">用户#{{ currentInstance.initiator_id }}</el-descriptions-item>
          <el-descriptions-item label="当前步骤">{{ currentInstance.current_step }}</el-descriptions-item>
          <el-descriptions-item label="发起时间">{{ formatDate(currentInstance.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ currentInstance.completed_at ? formatDate(currentInstance.completed_at) : '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 步骤时间线 -->
        <h4 style="margin-bottom: 12px">审批步骤</h4>
        <el-timeline v-if="currentInstance.steps?.length">
          <el-timeline-item
            v-for="step in currentInstance.steps"
            :key="step.id"
            :timestamp="step.completed_at ? formatDate(step.completed_at) : '待处理'"
            placement="top"
            :type="getStepTimelineType(step)"
          >
            <el-card shadow="never">
              <div style="display: flex; justify-content: space-between; align-items: center">
                <div>
                  <strong>步骤{{ step.step_no }}: {{ step.name }}</strong>
                  <span style="margin-left: 8px; color: #999; font-size: 13px">{{ stepTypeLabel(step.step_type) }}</span>
                </div>
                <el-tag :type="getStepStatusColor(step.status)" size="small">{{ stepStatusLabel(step.status) }}</el-tag>
              </div>
              <div v-if="step.remark" style="margin-top: 8px; color: #666; font-size: 13px">备注: {{ step.remark }}</div>
              <!-- 审批操作按钮 -->
              <div v-if="canActOn(step)" style="margin-top: 12px">
                <el-button type="success" size="small" @click="handleAction(step, 'approve')">通过</el-button>
                <el-button type="danger" size="small" @click="handleAction(step, 'reject')">驳回</el-button>
                <el-button size="small" @click="handleAction(step, 'return')">退回上一步</el-button>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无步骤数据" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { workflowsApi } from '@/api/workflows'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const instances = ref<any[]>([])
const filterStatus = ref('')
const detailDialogVisible = ref(false)
const currentInstance = ref<any>(null)

const statusLabels: Record<string, string> = {
  running: '运行中',
  completed: '已完成',
  rejected: '已驳回',
  cancelled: '已取消',
  suspended: '已挂起',
}

const getStatusColor = (s: string) => ({
  running: 'primary',
  completed: 'success',
  rejected: 'danger',
  cancelled: 'info',
  suspended: 'warning',
}[s] || 'info') as any

const stepTypeLabel = (t: string) => ({
  start: '开始',
  review: '审查',
  approval: '审批',
  cc: '抄送',
  condition: '条件',
  end: '结束',
}[t] || t)

const stepStatusLabel = (s: string) => ({
  pending: '待处理',
  approved: '已通过',
  rejected: '已驳回',
  skipped: '已跳过',
}[s] || s)

const getStepStatusColor = (s: string) => ({
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  skipped: 'info',
}[s] || 'info') as any

const getStepTimelineType = (step: any) => {
  if (step.status === 'approved') return 'success'
  if (step.status === 'rejected') return 'danger'
  if (step.status === 'pending') return 'primary'
  return 'info'
}

const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

const getProgress = (row: any) => {
  if (!row.steps?.length) return 0
  const done = row.steps.filter((s: any) => s.status === 'approved').length
  return Math.round((done / row.steps.length) * 100)
}

const goToContract = (id: number) => {
  router.push(`/contracts/${id}`)
}

const canActOn = (step: any) => {
  if (currentInstance.value?.status !== 'running') return false
  if (step.status !== 'pending') return false
  // 步骤号等于当前步骤
  if (step.step_no !== currentInstance.value?.current_step) return false
  // 没有指定 assignee 或者 assignee 是当前用户
  if (!step.assignee_id) return true
  return step.assignee_id === userStore.userInfo?.id
}

const viewDetail = async (row: any) => {
  try {
    const detail = await workflowsApi.getInstance(row.id) as any
    currentInstance.value = detail
    detailDialogVisible.value = true
  } catch {
    ElMessage.error('获取详情失败')
  }
}

const handleAction = async (step: any, action: string) => {
  let remark = ''
  if (action !== 'approve') {
    try {
      const res = await ElMessageBox.prompt('请输入备注', '审批意见', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputType: 'textarea',
      })
      remark = res.value || ''
    } catch {
      return
    }
  } else {
    try {
      const res = await ElMessageBox.prompt('通过备注（可选）', '审批意见', {
        confirmButtonText: '确定',
        cancelButtonText: '跳过',
        inputType: 'textarea',
      })
      remark = res.value || ''
    } catch {
      // 跳过备注
    }
  }

  try {
    await workflowsApi.stepAction(currentInstance.value.id, step.id, { action, remark })
    ElMessage.success('操作成功')
    // 刷新详情
    const detail = await workflowsApi.getInstance(currentInstance.value.id) as any
    currentInstance.value = detail
    await loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (filterStatus.value) params.status = filterStatus.value
    instances.value = (await workflowsApi.getInstances(params) as any) || []
  } catch {
    instances.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mb-16 {
  margin-bottom: 16px;
}
</style>
