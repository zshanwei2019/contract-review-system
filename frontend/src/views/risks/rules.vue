<template>
  <div class="risk-rules">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>风险规则</span>
          <div>
            <el-button type="success" icon="Refresh" @click="handleInitRules" :loading="initLoading">初始化规则</el-button>
            <el-button type="primary" icon="Plus" @click="showDialog = true">新建规则</el-button>
          </div>
        </div>
      </template>
      
      <el-table v-loading="loading" :data="rules" stripe border>
        <el-table-column prop="name" label="规则名称" min-width="200" />
        <el-table-column prop="category.name" label="分类" width="120" />
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getRiskColor(row.risk_level)" size="small">{{ getRiskLabel(row.risk_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="适用类型" width="140">
          <template #default="{ row }">
            <el-tag size="small" type="primary">{{ formatContractType(row.contract_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-dialog v-model="showDialog" :title="editingRule ? '编辑规则' : '新建规则'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则名称" required>
          <el-input v-model="form.name" placeholder="请输入规则名称" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category_id" style="width: 100%">
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级" required>
          <el-select v-model="form.risk_level" style="width: 100%">
            <el-option label="高风险" value="high" />
            <el-option label="中风险" value="medium" />
            <el-option label="低风险" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="规则描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="规则表达式">
          <el-input v-model="form.rule_expression" type="textarea" :rows="3" placeholder="正则表达式或关键词" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { risksApi } from '@/api/risks'
import { ElMessage } from 'element-plus'
import { formatRiskRuleContractType, riskLevelTagType, riskLevelLabels } from '@/types/risk'

const loading = ref(false)
const initLoading = ref(false)
const rules = ref<any[]>([])
const categories = ref<any[]>([])
const showDialog = ref(false)
const editingRule = ref<any>(null)
const form = reactive({ name: '', category_id: null, risk_level: 'medium', description: '', rule_expression: '' })

const getRiskColor = (level: string) => riskLevelTagType[level] || 'info' as any
const getRiskLabel = (level: string) => riskLevelLabels[level] || level
const formatContractType = (value: string | null) => formatRiskRuleContractType(value)

const fetchData = async () => {
  loading.value = true
  try {
    const [rulesRes, catsRes]: any[] = await Promise.all([
      risksApi.getRules({ page: 1, page_size: 100 }),
      risksApi.getCategories()
    ])
    rules.value = rulesRes.items || []
    categories.value = catsRes || []
  } catch {} finally { loading.value = false }
}

const handleEdit = (row: any) => {
  editingRule.value = row
  Object.assign(form, row)
  showDialog.value = true
}

const handleSave = async () => {
  try {
    if (editingRule.value) {
      await risksApi.updateRule(editingRule.value.id, form)
    } else {
      await risksApi.createRule(form)
    }
    ElMessage.success('保存成功')
    showDialog.value = false
    fetchData()
  } catch { ElMessage.error('保存失败') }
}

const handleInitRules = async () => {
  try {
    initLoading.value = true
    const res: any = await risksApi.initRules()
    ElMessage.success(res.message || '初始化成功')
    await fetchData()
  } catch { ElMessage.error('初始化失败') } finally { initLoading.value = false }
}

onMounted(() => { fetchData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
