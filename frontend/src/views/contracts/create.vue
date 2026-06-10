<template>
  <div class="contract-create">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>新建合同</span>
          <el-button icon="Back" @click="router.back()">返回</el-button>
        </div>
      </template>
      
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        style="max-width: 800px"
      >
        <el-form-item label="合同名称" prop="title">
          <el-input v-model="form.title" placeholder="请输入合同名称" />
        </el-form-item>
        
        <el-form-item label="合同类型" prop="contract_type">
          <el-select v-model="form.contract_type" placeholder="请选择合同类型" style="width: 100%">
            <el-option
              v-for="(label, value) in contractTypeLabels"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="甲方" prop="party_a">
              <el-input v-model="form.party_a" placeholder="请输入甲方名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="乙方" prop="party_b">
              <el-input v-model="form.party_b" placeholder="请输入乙方名称" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同金额" prop="amount">
              <el-input-number
                v-model="form.amount"
                :min="0"
                :precision="2"
                :controls="false"
                placeholder="请输入金额"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="币种" prop="currency">
              <el-select v-model="form.currency" style="width: 100%">
                <el-option label="人民币" value="CNY" />
                <el-option label="美元" value="USD" />
                <el-option label="欧元" value="EUR" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="签订日期" prop="sign_date">
              <el-date-picker
                v-model="form.sign_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="生效日期" prop="effective_date">
              <el-date-picker
                v-model="form.effective_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="到期日期" prop="expiry_date">
              <el-date-picker
                v-model="form.expiry_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属部门" prop="department">
              <el-input v-model="form.department" placeholder="请输入部门" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目名称" prop="project_name">
              <el-input v-model="form.project_name" placeholder="请输入项目名称" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="合同描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入合同描述"
          />
        </el-form-item>
        
        <el-form-item label="附件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="5"
            :on-change="handleFileChange"
            accept=".pdf,.doc,.docx,.xls,.xlsx"
          >
            <el-button icon="Upload">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 PDF、Word、Excel 文件，单个文件不超过 50MB</div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSubmit">
            保存
          </el-button>
          <el-button type="success" :loading="loading" @click="handleSubmitAndReview">
            保存并提交审查
          </el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'
import { contractTypeLabels } from '@/types/contract'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules, UploadFile } from 'element-plus'

const router = useRouter()
const formRef = ref<FormInstance>()
// @ts-ignore - used in template ref
const uploadRef = ref()
const loading = ref(false)
const fileList = ref<File[]>([])

const form = reactive({
  title: '',
  contract_type: '' as string,
  party_a: '',
  party_b: '',
  amount: undefined as number | undefined,
  currency: 'CNY',
  sign_date: '',
  effective_date: '',
  expiry_date: '',
  department: '',
  project_name: '',
  description: '',
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入合同名称', trigger: 'blur' }],
  contract_type: [{ required: true, message: '请选择合同类型', trigger: 'change' }],
}

const handleFileChange = (file: UploadFile) => {
  if (file.raw) {
    fileList.value.push(file.raw)
  }
}

const buildFormData = () => {
  return {
    title: form.title,
    contract_type: form.contract_type as string,
    party_a: form.party_a || null,
    party_b: form.party_b || null,
    amount: form.amount ?? null,
    currency: form.currency,
    sign_date: form.sign_date || null,
    effective_date: form.effective_date || null,
    expiry_date: form.expiry_date || null,
    department: form.department || null,
    project_name: form.project_name || null,
    description: form.description || null,
  }
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  
  loading.value = true
  try {
    await contractsApi.create(buildFormData() as any)
    ElMessage.success('合同创建成功')
    router.push('/contracts/list')
  } catch {
    ElMessage.error('创建失败')
  } finally {
    loading.value = false
  }
}

const handleSubmitAndReview = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  
  loading.value = true
  try {
    const res: any = await contractsApi.create(buildFormData() as any)
    await contractsApi.submit(res.id)
    ElMessage.success('合同已提交审查')
    router.push('/contracts/list')
  } catch {
    ElMessage.error('提交失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
