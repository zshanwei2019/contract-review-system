<template>
  <div class="workflow-definitions">
    <!-- 工作流定义列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="card-header-flex">
          <span>审批流程定义</span>
          <el-button type="primary" icon="Plus" @click="showCreateDialog = true">新建流程</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="definitions" stripe border>
        <el-table-column prop="name" label="流程名称" min-width="180" />
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="contract_type" label="适用合同类型" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ contractTypeLabel(row.contract_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewSteps(row)">查看步骤</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 步骤详情弹窗 -->
    <el-dialog v-model="stepsDialogVisible" :title="`流程步骤 - ${currentDefinition?.name || ''}`" width="600px">
      <el-timeline v-if="parsedSteps.length">
        <el-timeline-item v-for="(step, idx) in parsedSteps" :key="idx" :timestamp="`步骤 ${step.step_no}`" placement="top">
          <el-card shadow="never">
            <p><strong>{{ step.name }}</strong></p>
            <p style="color: #999; font-size: 13px;">类型: {{ stepTypeLabel(step.step_type) }}</p>
          </el-card>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无步骤定义" />
    </el-dialog>

    <!-- 新建流程弹窗 -->
    <el-dialog v-model="showCreateDialog" title="新建审批流程" width="700px">
      <el-form :model="newDefinition" label-width="120px">
        <el-form-item label="流程名称" required>
          <el-input v-model="newDefinition.name" placeholder="如：标准合同审批流程" />
        </el-form-item>
        <el-form-item label="流程编码" required>
          <el-input v-model="newDefinition.code" placeholder="如：standard-approval" />
        </el-form-item>
        <el-form-item label="适用合同类型">
          <el-select v-model="newDefinition.contract_type" placeholder="选择合同类型" clearable style="width: 100%">
            <el-option label="通用" value="" />
            <el-option label="采购合同" value="procurement" />
            <el-option label="销售合同" value="sales" />
            <el-option label="外协合同" value="outsourcing" />
            <el-option label="设备合同" value="equipment" />
            <el-option label="租赁合同" value="lease" />
            <el-option label="保密协议" value="nda" />
            <el-option label="服务合同" value="service" />
            <el-option label="工程合同" value="construction" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newDefinition.description" type="textarea" :rows="2" placeholder="流程说明" />
        </el-form-item>
        <el-form-item label="审批步骤">
          <div v-for="(step, idx) in newDefinition.steps" :key="idx" class="step-row">
            <el-input v-model="step.name" placeholder="步骤名称" style="width: 160px" />
            <el-select v-model="step.step_type" placeholder="类型" style="width: 120px; margin-left: 8px">
              <el-option label="审查" value="review" />
              <el-option label="审批" value="approval" />
              <el-option label="抄送" value="cc" />
            </el-select>
            <el-button type="danger" icon="Delete" circle size="small" @click="newDefinition.steps.splice(idx, 1)" style="margin-left: 8px" />
          </div>
          <el-button type="primary" link icon="Plus" @click="addStep">添加步骤</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { workflowsApi } from '@/api/workflows'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

const loading = ref(false)
const definitions = ref<any[]>([])
const showCreateDialog = ref(false)
const creating = ref(false)
const stepsDialogVisible = ref(false)
const currentDefinition = ref<any>(null)

const newDefinition = reactive({
  name: '',
  code: '',
  contract_type: '',
  description: '',
  steps: [
    { step_no: 1, name: '部门初审', step_type: 'review' },
    { step_no: 2, name: '法务审查', step_type: 'review' },
    { step_no: 3, name: '领导审批', step_type: 'approval' },
  ],
})

const parsedSteps = computed(() => {
  if (!currentDefinition.value?.steps_definition) return []
  try {
    return JSON.parse(currentDefinition.value.steps_definition)
  } catch {
    return []
  }
})

const contractTypeLabel = (t: string) => {
  const map: Record<string, string> = {
    '': '通用',
    procurement: '采购合同',
    sales: '销售合同',
    outsourcing: '外协合同',
    equipment: '设备合同',
    lease: '租赁合同',
    nda: '保密协议',
    service: '服务合同',
    construction: '工程合同',
    other: '其他',
  }
  return map[t] || t || '通用'
}

const stepTypeLabel = (t: string) => {
  const map: Record<string, string> = {
    start: '开始',
    review: '审查',
    approval: '审批',
    cc: '抄送',
    condition: '条件判断',
    end: '结束',
  }
  return map[t] || t
}

const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

const addStep = () => {
  newDefinition.steps.push({
    step_no: newDefinition.steps.length + 1,
    name: '',
    step_type: 'review',
  })
}

const viewSteps = (row: any) => {
  currentDefinition.value = row
  stepsDialogVisible.value = true
}

const handleCreate = async () => {
  if (!newDefinition.name || !newDefinition.code) {
    ElMessage.warning('请填写流程名称和编码')
    return
  }
  creating.value = true
  try {
    await workflowsApi.createDefinition({
      name: newDefinition.name,
      code: newDefinition.code,
      contract_type: newDefinition.contract_type || null,
      description: newDefinition.description,
      steps_definition: JSON.stringify(newDefinition.steps.map((s, i) => ({ ...s, step_no: i + 1 }))),
    })
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    newDefinition.name = ''
    newDefinition.code = ''
    newDefinition.description = ''
    newDefinition.steps = [
      { step_no: 1, name: '部门初审', step_type: 'review' },
      { step_no: 2, name: '法务审查', step_type: 'review' },
      { step_no: 3, name: '领导审批', step_type: 'approval' },
    ]
    await loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

const loadData = async () => {
  loading.value = true
  try {
    definitions.value = (await workflowsApi.getDefinitions() as any) || []
  } catch {
    definitions.value = []
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
.step-row {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
}
</style>
