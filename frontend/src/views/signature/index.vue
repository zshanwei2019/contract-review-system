<template>
  <div class="signature-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 签章请求 -->
      <el-tab-pane label="签章请求" name="requests">
        <div class="search-bar">
          <el-input v-model="filter.signer_name" placeholder="签署人" clearable style="width: 160px" @keyup.enter="loadRequests" />
          <el-select v-model="filter.status" placeholder="状态" clearable style="width: 120px" @change="loadRequests">
            <el-option label="待签署" value="pending" />
            <el-option label="已签署" value="signed" />
            <el-option label="已驳回" value="rejected" />
            <el-option label="已撤销" value="revoked" />
            <el-option label="已过期" value="expired" />
          </el-select>
          <el-button type="primary" @click="loadRequests">搜索</el-button>
          <el-button type="success" @click="showCreate = true">发起签章</el-button>
        </div>

        <el-table :data="requests" v-loading="loading" stripe style="margin-top: 16px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="signer_name" label="签署人" width="120" />
          <el-table-column prop="signature_type" label="类型" width="80">
            <template #default="{ row }">
              {{ row.signature_type === 'enterprise' ? '企业' : '个人' }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="position" label="签章位置" min-width="150" show-overflow-tooltip />
          <el-table-column prop="signed_at" label="签署时间" width="170">
            <template #default="{ row }">{{ formatTime(row.signed_at) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" link type="success" @click="handleSign(row.id)">签署</el-button>
              <el-button v-if="row.status === 'pending'" link type="danger" @click="handleReject(row.id)">驳回</el-button>
              <el-button v-if="row.status !== 'revoked'" link type="warning" @click="handleRevoke(row.id)">撤销</el-button>
              <el-button v-if="row.status === 'signed'" link type="primary" @click="handleVerify(row.id)">验证</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-if="total > 0"
          v-model:current-page="page"
          :page-size="20"
          :total="total"
          layout="total, prev, pager, next"
          style="margin-top: 16px; justify-content: flex-end"
          @current-change="loadRequests"
        />
      </el-tab-pane>

      <!-- 印章管理 -->
      <el-tab-pane label="印章管理" name="seals">
        <div class="search-bar">
          <el-button type="success" @click="showSealCreate = true">添加印章</el-button>
        </div>
        <el-table :data="seals" v-loading="sealLoading" stripe style="margin-top: 16px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="印章名称" width="180" />
          <el-table-column prop="seal_type" label="类型" width="120">
            <template #default="{ row }">{{ sealTypeLabel(row.seal_type) }}</template>
          </el-table-column>
          <el-table-column prop="certificate_sn" label="证书编号" width="200" show-overflow-tooltip />
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link @click="handleToggleSeal(row.id)">{{ row.is_active ? '停用' : '启用' }}</el-button>
              <el-button link type="danger" @click="handleDeleteSeal(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 发起签章弹窗 -->
    <el-dialog v-model="showCreate" title="发起签章请求" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="选择合同" required>
          <el-select v-model="createForm.contract_id" placeholder="选择合同" filterable style="width: 100%">
            <el-option v-for="c in contracts" :key="c.id" :label="`#${c.id} ${c.title}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="签署人" required>
          <el-input v-model="createForm.signer_name" placeholder="签署人姓名" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="createForm.signer_email" placeholder="签署人邮箱" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="createForm.signer_phone" placeholder="签署人手机" />
        </el-form-item>
        <el-form-item label="签章类型">
          <el-radio-group v-model="createForm.signature_type">
            <el-radio value="enterprise">企业签章</el-radio>
            <el-radio value="personal">个人签章</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="签章位置">
          <el-input v-model="createForm.position" placeholder="如：末页盖章处" />
        </el-form-item>
        <el-form-item label="选择印章">
          <el-select v-model="createForm.seal_id" placeholder="选择印章" clearable style="width: 100%">
            <el-option v-for="s in seals.filter(s => s.is_active)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确认发起</el-button>
      </template>
    </el-dialog>

    <!-- 添加印章弹窗 -->
    <el-dialog v-model="showSealCreate" title="添加印章" width="460px">
      <el-form :model="sealForm" label-width="100px">
        <el-form-item label="印章名称" required>
          <el-input v-model="sealForm.name" placeholder="如：公司公章" />
        </el-form-item>
        <el-form-item label="印章类型" required>
          <el-select v-model="sealForm.seal_type" style="width: 100%">
            <el-option label="公章" value="official" />
            <el-option label="合同章" value="contract" />
            <el-option label="财务章" value="finance" />
            <el-option label="法人章" value="legal" />
          </el-select>
        </el-form-item>
        <el-form-item label="印章图片URL" required>
          <el-input v-model="sealForm.image_url" placeholder="印章图片地址" />
        </el-form-item>
        <el-form-item label="证书编号">
          <el-input v-model="sealForm.certificate_sn" placeholder="数字证书序列号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSealCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreateSeal">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- 验证结果弹窗 -->
    <el-dialog v-model="verifyVisible" title="签章验证" width="500px">
      <el-descriptions :column="1" border v-if="verifyResult">
        <el-descriptions-item label="验证结果">
          <el-tag type="success" size="small">有效 ✓</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="签署人">{{ verifyResult.signer_name }}</el-descriptions-item>
        <el-descriptions-item label="证书编号">{{ verifyResult.certificate_sn }}</el-descriptions-item>
        <el-descriptions-item label="颁发机构">{{ verifyResult.certificate_issuer }}</el-descriptions-item>
        <el-descriptions-item label="签署时间">{{ formatTime(verifyResult.signed_at) }}</el-descriptions-item>
        <el-descriptions-item label="哈希值">
          <span style="font-family: monospace; font-size: 12px; word-break: break-all">{{ verifyResult.hash_value }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { signatureApi } from '@/api/signature'
import { contractsApi } from '@/api/contracts'

const activeTab = ref('requests')
const loading = ref(false)
const requests = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const filter = reactive({ signer_name: '', status: '' })

const sealLoading = ref(false)
const seals = ref<any[]>([])
const contracts = ref<any[]>([])

const showCreate = ref(false)
const createForm = reactive<any>({
  contract_id: 1, signer_name: '', signer_email: '', signer_phone: '',
  signature_type: 'enterprise', position: '', seal_id: null, remark: '',
})

const showSealCreate = ref(false)
const sealForm = reactive<any>({ name: '', seal_type: 'official', image_url: '', certificate_sn: '' })

const verifyVisible = ref(false)
const verifyResult = ref<any>(null)

function formatTime(val: string) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}
function statusLabel(s: string) {
  return { pending: '待签署', signed: '已签署', rejected: '已驳回', revoked: '已撤销', expired: '已过期' }[s] || s
}
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function statusTag(s: string): TagType {
  return ({ pending: 'warning', signed: 'success', rejected: 'danger', revoked: 'info', expired: 'info' } as const)[s] || 'info'
}
function sealTypeLabel(s: string) {
  return { official: '公章', contract: '合同章', finance: '财务章', legal: '法人章' }[s] || s
}

async function loadRequests() {
  loading.value = true
  try {
    const params: any = { page: page.value, size: 20 }
    if (filter.signer_name) params.signer_name = filter.signer_name
    if (filter.status) params.status = filter.status
    const [listRes, countRes] = await Promise.all([
      signatureApi.listRequests(params),
      signatureApi.countRequests(params),
    ])
    requests.value = listRes.data || []
    total.value = countRes.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadContracts() {
  try {
    const res = await contractsApi.list({ page: 1, page_size: 100 })
    contracts.value = res.data?.items || res.data || []
  } catch {}
}

async function loadSeals() {
  sealLoading.value = true
  try {
    const res = await signatureApi.listSeals()
    seals.value = res.data || []
  } catch {} finally { sealLoading.value = false }
}

async function handleCreate() {
  try {
    await signatureApi.createRequest(createForm)
    ElMessage.success('签章请求已发起')
    showCreate.value = false
    loadRequests()
  } catch (e: any) { ElMessage.error(e.message || '发起失败') }
}

async function handleSign(id: number) {
  await ElMessageBox.confirm('确认签署此签章请求？', '提示')
  try {
    const res = await signatureApi.signRequest(id)
    ElMessage.success(`签署成功，证书编号: ${res.data.certificate_sn}`)
    loadRequests()
  } catch (e: any) { ElMessage.error(e.message || '签署失败') }
}

async function handleReject(id: number) {
  try {
    await signatureApi.rejectRequest(id)
    ElMessage.success('已驳回')
    loadRequests()
  } catch (e: any) { ElMessage.error(e.message || '操作失败') }
}

async function handleRevoke(id: number) {
  await ElMessageBox.confirm('确认撤销此签章？', '提示')
  try {
    await signatureApi.revokeRequest(id)
    ElMessage.success('已撤销')
    loadRequests()
  } catch (e: any) { ElMessage.error(e.message || '操作失败') }
}

async function handleVerify(id: number) {
  try {
    const res = await signatureApi.verifySignature(id)
    verifyResult.value = res.data
    verifyVisible.value = true
  } catch (e: any) { ElMessage.error(e.message || '验证失败') }
}

async function handleCreateSeal() {
  try {
    await signatureApi.createSeal(sealForm)
    ElMessage.success('印章已添加')
    showSealCreate.value = false
    loadSeals()
  } catch (e: any) { ElMessage.error(e.message || '添加失败') }
}

async function handleToggleSeal(id: number) {
  try {
    await signatureApi.toggleSeal(id)
    loadSeals()
  } catch (e: any) { ElMessage.error(e.message || '操作失败') }
}

async function handleDeleteSeal(id: number) {
  await ElMessageBox.confirm('确认删除此印章？', '提示')
  try {
    await signatureApi.deleteSeal(id)
    ElMessage.success('已删除')
    loadSeals()
  } catch (e: any) { ElMessage.error(e.message || '删除失败') }
}

onMounted(() => {
  loadRequests()
  loadSeals()
  loadContracts()
})
</script>

<style scoped>
.search-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>
