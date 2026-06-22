<template>
  <div class="template-library">
    <el-card class="search-card" shadow="never">
      <div class="search-bar">
        <el-select v-model="filterType" placeholder="合同类型" clearable style="width: 180px" @change="loadList">
          <el-option v-for="t in contractTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px" @change="loadList">
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="已归档" value="archived" />
        </el-select>
        <el-button type="primary" @click="loadList">搜索</el-button>
        <el-button type="success" @click="openDialog()">新增模板</el-button>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="name" label="模板名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="contract_type" label="合同类型" width="120">
          <template #default="{ row }">{{ typeLabel(row.contract_type) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="70" align="center" />
        <el-table-column prop="usage_count" label="使用次数" width="90" align="center" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="row.status === 'draft'" link type="success" @click="handlePublish(row)">发布</el-button>
            <el-button link type="primary" @click="openInstantiate(row)">使用</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模板' : '新增模板'" width="800px" top="5vh">
      <el-form :model="form" label-width="100px">
        <el-form-item label="模板名称" required>
          <el-input v-model="form.name" placeholder="模板名称" />
        </el-form-item>
        <el-form-item label="合同类型" required>
          <el-select v-model="form.contract_type" placeholder="选择类型" style="width: 100%">
            <el-option v-for="t in contractTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="模板描述" />
        </el-form-item>
        <el-form-item label="变量定义">
          <el-input v-model="form.variables" type="textarea" :rows="3" placeholder='JSON 格式，如 [{"name":"party_a","label":"甲方名称","required":true}]' />
        </el-form-item>
        <el-form-item label="模板内容" required>
          <el-input v-model="form.content" type="textarea" :rows="12" placeholder="模板正文，使用 {{变量名}} 作为占位符" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 实例化弹窗 -->
    <el-dialog v-model="instantiateVisible" title="从模板创建合同" width="600px">
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        填写变量值后，将生成一份新合同。
      </el-alert>
      <el-form :model="instantiateForm" label-width="140px">
        <el-form-item v-for="v in parsedVariables" :key="v.name" :label="v.label || v.name" :required="v.required">
          <el-input v-model="instantiateForm.variables[v.name]" :placeholder="`输入${v.label || v.name}`" />
        </el-form-item>
        <el-form-item label="合同标题">
          <el-input v-model="instantiateForm.title" placeholder="新合同标题（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="instantiateVisible = false">取消</el-button>
        <el-button type="primary" @click="handleInstantiate" :loading="instantiating">创建合同</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { templateApi } from '@/api/templates'

const loading = ref(false)
const saving = ref(false)
const instantiating = ref(false)
const tableData = ref<any[]>([])
const dialogVisible = ref(false)
const instantiateVisible = ref(false)
const editingId = ref<number | null>(null)
const currentTemplateId = ref<number | null>(null)

const filterType = ref('')
const filterStatus = ref('')

const form = ref({
  name: '',
  contract_type: '',
  content: '',
  description: '',
  variables: '',
})

const instantiateForm = reactive<{
  title: string
  variables: Record<string, string>
}>({
  title: '',
  variables: {},
})

const contractTypeOptions = [
  { label: '采购合同', value: 'purchase' },
  { label: '销售合同', value: 'sales' },
  { label: '服务合同', value: 'service' },
  { label: '租赁合同', value: 'lease' },
  { label: '劳动合同', value: 'labor' },
  { label: '工程合同', value: 'construction' },
  { label: '技术开发合同', value: 'tech' },
]

function typeLabel(val: string) {
  return contractTypeOptions.find(t => t.value === val)?.label || val
}
function statusLabel(val: string) {
  return { draft: '草稿', published: '已发布', archived: '已归档' }[val] || val
}
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function statusTagType(val: string): TagType {
  return ({ draft: 'info', published: 'success', archived: 'warning' } as const)[val] || 'info'
}

const parsedVariables = computed(() => {
  try {
    return JSON.parse(form.value.variables || '[]')
  } catch {
    return []
  }
})

async function loadList() {
  loading.value = true
  try {
    const res = await templateApi.list({
      contract_type: filterType.value || undefined,
      status: filterStatus.value || undefined,
    })
    tableData.value = res.data?.items || res.data || []
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) {
    editingId.value = row.id
    form.value = {
      name: row.name || '',
      contract_type: row.contract_type || '',
      content: row.content || '',
      description: row.description || '',
      variables: row.variables || '',
    }
  } else {
    editingId.value = null
    form.value = { name: '', contract_type: '', content: '', description: '', variables: '' }
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name || !form.value.contract_type || !form.value.content) {
    ElMessage.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await templateApi.update(editingId.value, form.value)
    } else {
      await templateApi.create(form.value)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadList()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handlePublish(row: any) {
  try {
    await templateApi.publish(row.id)
    ElMessage.success('已发布')
    loadList()
  } catch (e: any) {
    ElMessage.error(e.message || '发布失败')
  }
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除模板「${row.name}」？`, '确认', { type: 'warning' })
  try {
    await templateApi.delete(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

function openInstantiate(row: any) {
  currentTemplateId.value = row.id
  instantiateForm.title = ''
  instantiateForm.variables = {}
  // Parse variables from row
  try {
    const vars = JSON.parse(row.variables || '[]')
    vars.forEach((v: any) => {
      instantiateForm.variables[v.name] = ''
    })
  } catch {}
  instantiateVisible.value = true
}

async function handleInstantiate() {
  if (!currentTemplateId.value) return
  instantiating.value = true
  try {
    await templateApi.instantiate(currentTemplateId.value, {
      variables: instantiateForm.variables,
      title: instantiateForm.title || undefined,
    })
    ElMessage.success('合同已创建')
    instantiateVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    instantiating.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.search-card :deep(.el-card__body) { padding: 16px; }
.search-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>
