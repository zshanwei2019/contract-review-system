<template>
  <div class="workflow-instance-detail">
    <el-page-header @back="$router.back()" title="返回" content="流程实例详情" style="margin-bottom: 16px" />

    <el-row :gutter="16">
      <!-- 左侧：流程信息 -->
      <el-col :span="16">
        <el-card shadow="hover" style="margin-bottom: 16px">
          <template #header><span>基本信息</span></template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="实例ID">{{ instance?.id }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusColor(instance?.status)" size="small">{{ statusLabels[instance?.status] }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="合同ID">{{ instance?.contract_id }}</el-descriptions-item>
            <el-descriptions-item label="发起人ID">{{ instance?.initiator_id }}</el-descriptions-item>
            <el-descriptions-item label="当前步骤">{{ instance?.current_step || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(instance?.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="完成时间" v-if="instance?.completed_at">{{ formatDate(instance?.completed_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 审批步骤时间线 -->
        <el-card shadow="hover">
          <template #header><span>审批流程</span></template>
          <el-timeline v-if="instance?.steps?.length">
            <el-timeline-item
              v-for="step in instance.steps"
              :key="step.id"
              :timestamp="step.completed_at ? formatDate(step.completed_at) : '待处理'"
              :type="getStepTimelineType(step)"
              placement="top"
            >
              <el-card shadow="never" :class="{ 'step-active': step.status === 'pending' }">
                <div class="step-header">
                  <span class="step-name">步骤 {{ step.step_no }}: {{ step.name }}</span>
                  <el-tag :type="getStepStatusColor(step.status)" size="small">{{ stepStatusLabel(step.status) }}</el-tag>
                </div>
                <div class="step-body" v-if="step.remark">
                  <span class="step-label">备注:</span> {{ step.remark }}
                </div>
                <div class="step-body" v-if="step.assignee_id">
                  <span class="step-label">处理人:</span> 用户{{ step.assignee_id }}
                </div>

                <!-- 审批操作按钮 -->
                <div class="step-actions" v-if="canAct(step)">
                  <el-button type="success" icon="Check" size="small" @click="handleAction(step.id, 'approve')">通过</el-button>
                  <el-button type="danger" icon="Close" size="small" @click="handleAction(step.id, 'reject')">驳回</el-button>
                  <el-button type="warning" icon="Back" size="small" @click="handleAction(step.id, 'return')">退回上一步</el-button>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无步骤" />
        </el-card>
      </el-col>

      <!-- 右侧：操作面板 -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><span>快捷操作</span></template>
          <div style="display: flex; flex-direction: column; gap: 12px">
            <el-button type="primary" @click="$router.push(`/contracts/${instance?.contract_id}`)">
              查看合同详情
            </el-button>
            <el-button @click="loadData">刷新状态</el-button>
          </div>
        </el-card>

        <el-card shadow="hover" style="margin-top: 16px" v-if="actionHistory.length">
          <template #header><span>操作记录</span></template>
          <div v-for="(log, idx) in actionHistory" :key="idx" class="action-log">
            <el-tag :type="log.action === 'approve' ? 'success' : log.action === 'reject' ? 'danger' : 'warning'" size="small">
              {{ log.actionLabel }}
            </el-tag>
            <span class="log-text">{{ log.remark || '无备注' }}</span>
            <span class="log-time">{{ log.time }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 审批备注弹窗 -->
    <el-dialog v-model="actionDialogVisible" :title="actionDialogTitle" width="450px">
      <el-input v-model="actionRemark" type="textarea" :rows="3" placeholder="请输入审批备注（可选）" />
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="confirmAction">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { workflowsApi } from '@/api/workflows'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const instance = ref<any>(null)
const loading = ref(false)
const actionDialogVisible = ref(false)
const actionDialogTitle = ref('')
const actionRemark = ref('')
const acting = ref(false)
const pendingAction = ref<{ stepId: number; action: string } | null>(null)

const statusLabels: Record<string, string> = {
  running: '运行中',
  completed: '已完成',
  rejected: '已驳回',
  cancelled: '已取消',
  suspended: '已挂起',
}

const getStatusColor = (s?: string) => {
  const map: Record<string, string> = { running: 'primary', completed: 'success', rejected: 'danger', cancelled: 'info', suspended: 'warning' }
  return (map[s || ''] || 'info') as any
}

const stepStatusLabel = (s: string) => {
  const map: Record<string, string> = { pending: '待处理', approved: '已通过', rejected: '已驳回', skipped: '已跳过' }
  return map[s] || s
}

const getStepStatusColor = (s: string) => {
  const map: Record<string, string> = { pending: 'warning', approved: 'success', rejected: 'danger', skipped: 'info' }
  return (map[s] || 'info') as any
}

const getStepTimelineType = (step: any) => {
  if (step.status === 'approved') return 'success'
  if (step.status === 'rejected') return 'danger'
  if (step.status === 'pending') return 'warning'
  return 'info'
}

const formatDate = (d?: string) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '-'

const canAct = (step: any) => {
  if (instance.value?.status !== 'running') return false
  if (step.status !== 'pending') return false
  // 当前步骤才能操作
  if (step.step_no !== instance.value?.current_step) return false
  // 检查权限：assignee_id 匹配 或 admin
  if (step.assignee_id && step.assignee_id !== userStore.userInfo?.id) {
    return (userStore.userInfo?.roles || []).some((r: any) => r.name === 'admin' || r.name === 'superadmin')
  }
  return true
}

const actionHistory = computed(() => {
  if (!instance.value?.steps) return []
  return instance.value.steps
    .filter((s: any) => s.status !== 'pending' && s.completed_at)
    .map((s: any) => ({
      action: s.result,
      actionLabel: s.result === 'approve' ? '通过' : s.result === 'reject' ? '驳回' : '退回',
      remark: s.remark,
      time: formatDate(s.completed_at),
    }))
    .sort((a: any, b: any) => b.time.localeCompare(a.time))
})

const handleAction = (stepId: number, action: string) => {
  pendingAction.value = { stepId, action }
  actionDialogTitle.value = action === 'approve' ? '审批通过' : action === 'reject' ? '驳回' : '退回上一步'
  actionRemark.value = ''
  actionDialogVisible.value = true
}

const confirmAction = async () => {
  if (!pendingAction.value) return
  acting.value = true
  try {
    await workflowsApi.stepAction(instance.value.id, pendingAction.value.stepId, {
      action: pendingAction.value.action,
      remark: actionRemark.value || undefined,
    })
    ElMessage.success('操作成功')
    actionDialogVisible.value = false
    await loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  } finally {
    acting.value = false
  }
}

const loadData = async () => {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    instance.value = await workflowsApi.getInstance(id)
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.step-active {
  border-color: #409eff;
  background: #ecf5ff;
}
.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.step-name {
  font-weight: 600;
}
.step-body {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}
.step-label {
  color: #999;
}
.step-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.action-log {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}
.log-text {
  flex: 1;
  font-size: 13px;
  color: #666;
}
.log-time {
  font-size: 12px;
  color: #999;
}
</style>
