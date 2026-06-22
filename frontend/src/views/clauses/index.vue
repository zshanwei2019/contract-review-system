<template>
  <div class="clause-library">
    <!-- 搜索栏 -->
    <el-card class="search-card" shadow="never">
      <div class="search-bar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索条款标题或内容"
          clearable
          style="width: 280px"
          @keyup.enter="loadList"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="searchCategory" placeholder="条款类别" clearable style="width: 160px" @change="loadList">
          <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="searchContractType" placeholder="合同类型" clearable style="width: 160px" @change="loadList">
          <el-option v-for="t in contractTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-button type="primary" @click="loadList">搜索</el-button>
        <el-button type="success" @click="openDialog()">新增条款</el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="类别" width="120">
          <template #default="{ row }">
            <el-tag :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contract_type" label="适用类型" width="120">
          <template #default="{ row }">{{ row.contract_type || '通用' }}</template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险" width="80">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.risk_level)" size="small">{{ riskLabel(row.risk_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="usage_count" label="使用次数" width="90" align="center" />
        <el-table-column prop="tags" label="标签" min-width="150">
          <template #default="{ row }">
            <el-tag v-for="tag in (row.tags || '').split(',').filter(Boolean)" :key="tag" size="small" style="margin-right: 4px">{{ tag }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleFav(row)">
              {{ row.is_favorited ? '取消收藏' : '收藏' }}
            </el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑条款' : '新增条款'" width="700px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="条款标题" />
        </el-form-item>
        <el-form-item label="类别" required>
          <el-select v-model="form.category" placeholder="选择类别" style="width: 100%">
            <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="合同类型">
          <el-select v-model="form.contract_type" placeholder="适用合同类型（留空=通用）" clearable style="width: 100%">
            <el-option v-for="t in contractTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-radio-group v-model="form.risk_level">
            <el-radio value="low">低</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="high">高</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔，如：标准,推荐,必读" />
        </el-form-item>
        <el-form-item label="条款内容" required>
          <el-input v-model="form.content" type="textarea" :rows="8" placeholder="条款正文内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { clauseApi } from '@/api/clauses'

const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const searchKeyword = ref('')
const searchCategory = ref('')
const searchContractType = ref('')

const form = ref({
  title: '',
  category: '',
  content: '',
  contract_type: '',
  risk_level: 'low',
  tags: '',
})

const categoryOptions = [
  { label: '付款条款', value: 'payment' },
  { label: '违约责任', value: 'liability' },
  { label: '保密条款', value: 'confidentiality' },
  { label: '知识产权', value: 'intellectual' },
  { label: '终止条款', value: 'termination' },
  { label: '争议解决', value: 'dispute' },
  { label: '质保条款', value: 'warranty' },
  { label: '交付条款', value: 'delivery' },
  { label: '不可抗力', value: 'force_majeure' },
  { label: '其他', value: 'other' },
]

const contractTypeOptions = [
  { label: '采购合同', value: 'purchase' },
  { label: '销售合同', value: 'sales' },
  { label: '服务合同', value: 'service' },
  { label: '租赁合同', value: 'lease' },
  { label: '劳动合同', value: 'labor' },
  { label: '工程合同', value: 'construction' },
  { label: '技术开发合同', value: 'tech' },
]

function categoryLabel(val: string) {
  return categoryOptions.find(c => c.value === val)?.label || val
}
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function categoryTagType(val: string): TagType {
  const map: Record<string, TagType> = { payment: 'warning', liability: 'danger', confidentiality: 'info', termination: 'warning' }
  return map[val] || 'info'
}
function riskLabel(val: string) {
  return { low: '低', medium: '中', high: '高' }[val] || val
}
function riskTagType(val: string): TagType {
  return ({ low: 'success', medium: 'warning', high: 'danger' } as const)[val] || 'info'
}

async function loadList() {
  loading.value = true
  try {
    const res = await clauseApi.list({
      keyword: searchKeyword.value || undefined,
      category: searchCategory.value || undefined,
      contract_type: searchContractType.value || undefined,
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
    form.value = { ...row }
  } else {
    editingId.value = null
    form.value = { title: '', category: '', content: '', contract_type: '', risk_level: 'low', tags: '' }
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.title || !form.value.category || !form.value.content) {
    ElMessage.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await clauseApi.update(editingId.value, form.value)
    } else {
      await clauseApi.create(form.value)
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

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除「${row.title}」？`, '确认', { type: 'warning' })
  try {
    await clauseApi.delete(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function toggleFav(row: any) {
  try {
    await clauseApi.toggleFavorite(row.id, row.is_favorited)
    row.is_favorited = !row.is_favorited
    ElMessage.success(row.is_favorited ? '已收藏' : '已取消收藏')
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

onMounted(loadList)
</script>

<style scoped>
.search-card :deep(.el-card__body) { padding: 16px; }
.search-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>
