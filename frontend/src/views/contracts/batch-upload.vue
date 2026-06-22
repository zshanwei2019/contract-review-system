<template>
  <div class="batch-upload">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <div>
            <span>批量上传合同</span>
            <el-tag type="info" size="small" style="margin-left: 8px;">支持同时上传多个文件</el-tag>
          </div>
          <el-button icon="Back" @click="router.back()">返回</el-button>
        </div>
      </template>

      <!-- 上传区域 -->
      <el-upload
        ref="uploadRef"
        class="upload-dragger"
        drag
        multiple
        :auto-upload="false"
        :on-change="handleFileChange"
        :on-remove="() => {}"
        :before-upload="beforeUpload"
        accept=".pdf,.doc,.docx,.xls,.xlsx"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 PDF、Word、Excel 文件，单个文件不超过 50MB，最多同时上传 20 个文件
          </div>
        </template>
      </el-upload>

      <!-- 文件列表 -->
      <div v-if="fileList.length > 0" class="file-list-section">
        <div class="section-header">
          <h4>待上传文件 ({{ fileList.length }} 个)</h4>
          <div class="header-actions">
            <el-button type="danger" size="small" @click="handleClearFiles" :disabled="uploading">
              清空列表
            </el-button>
            <el-button 
              type="primary" 
              size="small" 
              @click="handleExtractAll" 
              :loading="extracting"
              :disabled="uploading"
            >
              智能识别全部
            </el-button>
          </div>
        </div>

        <el-table :data="fileList" border size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column label="文件名" min-width="200">
            <template #default="{ row }">
              <div class="file-name">
                <el-icon class="file-icon" :class="getFileIconClass(row.name)">
                  <Document />
                </el-icon>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="100">
            <template #default="{ row }">
              {{ formatFileSize(row.size) }}
            </template>
          </el-table-column>
          <el-table-column label="合同名称" width="200">
            <template #default="{ row, $index }">
              <el-input 
                v-model="row.contractTitle" 
                size="small" 
                placeholder="自动识别或手动输入"
                :disabled="uploading"
              />
            </template>
          </el-table-column>
          <el-table-column label="合同类型" width="150">
            <template #default="{ row, $index }">
              <el-select 
                v-model="row.contractType" 
                size="small" 
                placeholder="选择类型"
                :disabled="uploading"
              >
                <el-option
                  v-for="(label, value) in contractTypeLabels"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'pending'" type="info" size="small">待上传</el-tag>
              <el-tag v-else-if="row.status === 'extracting'" type="warning" size="small">
                <el-icon class="is-loading"><Loading /></el-icon> 识别中
              </el-tag>
              <el-tag v-else-if="row.status === 'ready'" type="success" size="small">已识别</el-tag>
              <el-tag v-else-if="row.status === 'uploading'" type="warning" size="small">
                <el-icon class="is-loading"><Loading /></el-icon> 上传中
              </el-tag>
              <el-tag v-else-if="row.status === 'success'" type="success" size="small">已完成</el-tag>
              <el-tag v-else-if="row.status === 'error'" type="danger" size="small">失败</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ $index }">
              <el-button 
                text 
                type="danger" 
                size="small" 
                @click="handleRemoveFile($index)"
                :disabled="uploading"
              >
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 上传控制 -->
        <div class="upload-controls">
          <div class="control-info">
            <el-checkbox v-model="autoSubmitReview" :disabled="uploading">
              上传后自动提交审查
            </el-checkbox>
            <el-checkbox v-model="autoQuantify" :disabled="uploading">
              审查完成后自动量化评估
            </el-checkbox>
          </div>
          <div class="control-actions">
            <el-button @click="router.back()" :disabled="uploading">取消</el-button>
            <el-button 
              type="primary" 
              :loading="uploading" 
              @click="handleUploadAll"
              :disabled="fileList.length === 0"
            >
              开始上传 ({{ fileList.length }} 个文件)
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 上传结果 -->
    <el-dialog v-model="showResult" title="批量上传结果" width="600px" :close-on-click-modal="false">
      <div class="upload-result">
        <el-result
          :icon="failedCount === 0 ? 'success' : 'warning'"
          :title="`上传完成`"
          :sub-title="`成功 ${successCount} 个，失败 ${failedCount} 个`"
        />
        
        <el-table :data="uploadResults" border size="small" max-height="300">
          <el-table-column label="文件" min-width="200">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.status === 'error' }">{{ row.fileName }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                {{ row.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="合同编号" width="150">
            <template #default="{ row }">
              {{ row.contractNo || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="错误信息" min-width="150">
            <template #default="{ row }">
              <span class="text-danger">{{ row.error || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showResult = false">关闭</el-button>
        <el-button type="primary" @click="router.push('/contracts/list')">
          查看合同列表
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'
import { contractTypeLabels } from '@/types/contract'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'

interface FileItem {
  raw: File
  name: string
  size: number
  contractTitle: string
  contractType: string
  status: 'pending' | 'extracting' | 'ready' | 'uploading' | 'success' | 'error'
  error?: string
}

interface UploadResult {
  fileName: string
  status: 'success' | 'error'
  contractId?: number
  contractNo?: string
  error?: string
}

const router = useRouter()
const fileList = ref<FileItem[]>([])
const uploading = ref(false)
const extracting = ref(false)
const autoSubmitReview = ref(false)
const autoQuantify = ref(false)
const showResult = ref(false)
const uploadResults = ref<UploadResult[]>([])

const successCount = ref(0)
const failedCount = ref(0)

// 文件变更处理
const handleFileChange = (uploadFile: UploadFile) => {
  if (uploadFile.raw) {
    const existing = fileList.value.find(f => f.name === uploadFile.name)
    if (existing) {
      ElMessage.warning(`文件 ${uploadFile.name} 已存在`)
      return
    }

    fileList.value.push({
      raw: uploadFile.raw,
      name: uploadFile.name,
      size: uploadFile.raw.size,
      contractTitle: uploadFile.name.replace(/\.[^/.]+$/, ''),
      contractType: '',
      status: 'pending',
    })
  }
}

// 移除文件
const handleRemoveFile = (index: number) => {
  fileList.value.splice(index, 1)
}

// 清空文件
const handleClearFiles = () => {
  fileList.value = []
}

// 上传前检查
const beforeUpload = (file: File) => {
  const isValidType = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ].includes(file.type)

  if (!isValidType) {
    ElMessage.error('只支持 PDF、Word、Excel 文件')
    return false
  }

  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }

  return true
}

// 智能识别全部
const handleExtractAll = async () => {
  extracting.value = true
  let completed = 0

  for (const fileItem of fileList.value) {
    if (fileItem.status === 'ready') continue

    fileItem.status = 'extracting'
    try {
      const info: any = await contractsApi.extractInfo(fileItem.raw)
      
      if (info.title) fileItem.contractTitle = info.title
      if (info.contract_type) fileItem.contractType = info.contract_type
      
      fileItem.status = 'ready'
      completed++
    } catch (err) {
      console.error(`识别失败: ${fileItem.name}`, err)
      fileItem.status = 'pending'
    }
  }

  extracting.value = false
  ElMessage.success(`识别完成，成功 ${completed} 个`)
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 获取文件图标样式
const getFileIconClass = (fileName: string) => {
  if (fileName.endsWith('.pdf')) return 'pdf-icon'
  if (fileName.endsWith('.doc') || fileName.endsWith('.docx')) return 'word-icon'
  if (fileName.endsWith('.xls') || fileName.endsWith('.xlsx')) return 'excel-icon'
  return ''
}

// 上传单个文件
const uploadSingleFile = async (fileItem: FileItem): Promise<UploadResult> => {
  try {
    fileItem.status = 'uploading'

    const formData = new FormData()
    formData.append('file', fileItem.raw)
    formData.append('title', fileItem.contractTitle || fileItem.name)
    if (fileItem.contractType) {
      formData.append('contract_type', fileItem.contractType)
    }

    const res: any = await contractsApi.createWithFile(formData)

    if (autoSubmitReview.value && res.id) {
      try {
        await contractsApi.submit(res.id)
      } catch (err) {
        console.error('自动提交审查失败:', err)
      }
    }

    fileItem.status = 'success'
    return {
      fileName: fileItem.name,
      status: 'success',
      contractId: res.id,
      contractNo: res.contract_no,
    }
  } catch (err: any) {
    fileItem.status = 'error'
    fileItem.error = err.message || '上传失败'
    return {
      fileName: fileItem.name,
      status: 'error',
      error: err.message || '上传失败',
    }
  }
}

// 上传全部
const handleUploadAll = async () => {
  const untyped = fileList.value.filter(f => !f.contractType)
  if (untyped.length > 0) {
    await ElMessageBox.confirm(
      `有 ${untyped.length} 个文件未选择合同类型，确定继续上传？`,
      '提示',
      { type: 'warning' }
    )
  }

  uploading.value = true
  uploadResults.value = []
  successCount.value = 0
  failedCount.value = 0

  for (const fileItem of fileList.value) {
    const result = await uploadSingleFile(fileItem)
    uploadResults.value.push(result)

    if (result.status === 'success') {
      successCount.value++
    } else {
      failedCount.value++
    }
  }

  uploading.value = false
  showResult.value = true
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-dragger {
  margin-bottom: 24px;
}

.upload-dragger :deep(.el-upload-dragger) {
  padding: 40px;
}

.file-list-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.file-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  font-size: 18px;
}

.file-icon.pdf-icon {
  color: #f56c6c;
}

.file-icon.word-icon {
  color: #409eff;
}

.file-icon.excel-icon {
  color: #67c23a;
}

.upload-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.control-info {
  display: flex;
  gap: 16px;
}

.control-actions {
  display: flex;
  gap: 8px;
}

.upload-result {
  padding: 0 16px;
}

.text-danger {
  color: #f56c6c;
}
</style>
