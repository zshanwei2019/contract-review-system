<template>
  <div class="agent-dashboard">
    <!-- 监控告警卡片 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📊 监控告警</span>
          <el-button type="primary" text @click="refreshAlerts">刷新</el-button>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-statistic title="已过期合同" :value="alerts.overdue_contracts?.count || 0">
            <template #suffix>
              <el-tag type="danger" size="small" v-if="alerts.overdue_contracts?.count">需处理</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="8">
          <el-statistic title="即将到期" :value="alerts.expiring_contracts?.count || 0">
            <template #suffix>
              <el-tag type="warning" size="small" v-if="alerts.expiring_contracts?.count">关注</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="8">
          <el-statistic title="待审查合同" :value="alerts.pending_reviews?.count || 0">
            <template #suffix>
              <el-tag type="info" size="small" v-if="alerts.pending_reviews?.count">待处理</el-tag>
            </template>
          </el-statistic>
        </el-col>
      </el-row>
      <el-alert v-if="alerts.summary" :title="alerts.summary" :type="alerts.total_alerts > 0 ? 'warning' : 'success'" show-icon :closable="false" style="margin-top: 16px" />
    </el-card>

    <!-- AI配置测试（仅管理员可见） -->
    <el-card v-if="isAdmin" shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span>⚙️ AI配置</span>
          <div>
            <el-button type="primary" @click="showAIConfigDialog = true">配置AI</el-button>
            <el-button @click="testAIConnection" :loading="testing">测试连接</el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="API地址">{{ aiConfig.base_url || '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ aiConfig.model || '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="API Key">{{ aiConfig.has_key ? '已配置' : '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="aiConfig.status === 'ok' ? 'success' : 'danger'">{{ aiConfig.status === 'ok' ? '正常' : '未连接' }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog v-model="showAIConfigDialog" title="AI配置" width="500px">
      <el-form :model="aiConfigForm" label-width="100px">
        <el-form-item label="API地址"><el-input v-model="aiConfigForm.base_url" placeholder="https://api.openai.com/v1" /></el-form-item>
        <el-form-item label="模型"><el-input v-model="aiConfigForm.model" placeholder="gpt-4-turbo-preview" /></el-form-item>
        <el-form-item label="API Key"><el-input v-model="aiConfigForm.api_key" type="password" show-password placeholder="sk-..." /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAIConfigDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAIConfig" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Agent列表 -->
    <el-card shadow="hover" class="section-card">
      <template #header><span>🤖 AI审查Agent</span></template>
      <el-row :gutter="20">
        <el-col :span="8" v-for="agent in agents" :key="agent.id">
          <el-card shadow="never" class="agent-card">
            <div class="agent-info">
              <span class="agent-icon">{{ agent.icon }}</span>
              <div><h4>{{ agent.name }}</h4><p>{{ agent.focus }}</p></div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 🔥 RAG 条款检索 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span>🔍 RAG 条款检索</span>
          <div>
            <el-button type="primary" size="small" @click="loadRagStats">刷新统计</el-button>
            <el-button v-if="isAdmin" size="small" @click="handleRebuild" :loading="rebuilding">重建向量库</el-button>
          </div>
        </div>
      </template>

      <!-- RAG 统计 -->
      <el-row :gutter="20" style="margin-bottom: 16px">
        <el-col :span="6"><el-statistic title="向量库总数" :value="ragStats.total || 0" /></el-col>
        <el-col :span="6"><el-statistic title="审查意见" :value="ragByType('review_opinion')" /></el-col>
        <el-col :span="6"><el-statistic title="法律知识" :value="ragByType('knowledge')" /></el-col>
        <el-col :span="6"><el-statistic title="人工修正" :value="ragByType('correction')" /></el-col>
      </el-row>

      <!-- 检索框 -->
      <el-input v-model="ragQuery" placeholder="输入条款文本检索历史类似案例..." type="textarea" :rows="3" style="margin-bottom: 12px" />
      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <el-select v-model="ragContractType" placeholder="合同类型(可选)" clearable size="small" style="width: 160px">
          <el-option label="采购合同" value="PROCUREMENT" />
          <el-option label="租赁合同" value="LEASE" />
          <el-option label="服务合同" value="SERVICE" />
          <el-option label="销售合同" value="SALES" />
          <el-option label="劳动合同" value="LABOR" />
        </el-select>
        <el-button type="primary" @click="searchRAG" :loading="ragSearching">检索</el-button>
        <el-button @click="ragQuery = ''; ragResults = []">清空</el-button>
      </div>

      <!-- 检索结果 -->
      <div v-if="ragResults.length > 0">
        <el-divider content-position="left">检索结果 ({{ ragResults.length }} 条)</el-divider>
        <div v-for="r in ragResults" :key="r.id" class="rag-result-item">
          <div class="rag-result-header">
            <el-tag :type="similarityTagType(r.similarity)" size="small">{{ (r.similarity * 100).toFixed(0) }}% 相似</el-tag>
            <el-tag v-if="r.risk_level" :type="riskTagType(r.risk_level)" size="small" style="margin-left: 4px">{{ riskLabel(r.risk_level) }}</el-tag>
            <el-tag type="info" size="small" style="margin-left: 4px">{{ sourceLabel(r.source_type) }}</el-tag>
          </div>
          <div class="rag-result-text"><strong>条款:</strong> {{ r.clause_text?.substring(0, 200) }}</div>
          <div v-if="r.suggestion_text" class="rag-result-suggestion"><strong>建议:</strong> {{ r.suggestion_text?.substring(0, 300) }}</div>
          <div v-if="r.legal_basis" class="rag-result-legal"><strong>依据:</strong> {{ r.legal_basis?.substring(0, 200) }}</div>
        </div>
      </div>
      <el-empty v-else-if="ragSearched" description="未检索到相关条款 (相似度阈值 55%)" />
    </el-card>

    <!-- 知识库 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📚 领域知识库</span>
          <div>
            <el-select v-model="knowledgeType" style="width: 120px; margin-right: 8px" size="small">
              <el-option label="法律法规" value="laws" />
              <el-option label="合规规则" value="compliance" />
            </el-select>
            <el-button type="primary" size="small" @click="loadKnowledge">查询</el-button>
          </div>
        </div>
      </template>
      <div v-if="knowledgeItems.length > 0">
        <el-collapse>
          <el-collapse-item v-for="item in knowledgeItems" :key="item.id" :title="item.title">
            <pre class="knowledge-content">{{ item.content }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
      <el-empty v-else description="暂无知识库数据">
        <el-button type="primary" @click="initKnowledge">初始化知识库</el-button>
      </el-empty>
    </el-card>

    <!-- 反馈统计 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📈 反馈学习统计</span>
          <el-tag v-if="ragByType('correction') > 0" type="success" size="small" style="margin-left: 8px">{{ ragByType('correction') }} 条已回流 RAG</el-tag>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="6"><el-statistic title="总修正数" :value="correctionStats.total_corrections || 0" /></el-col>
        <el-col :span="6"><el-statistic title="已学习" :value="correctionStats.learned || 0" /></el-col>
        <el-col :span="6"><el-statistic title="待学习" :value="correctionStats.pending || 0" /></el-col>
        <el-col :span="6"><el-statistic title="学习率" :value="learningRate" suffix="%" /></el-col>
      </el-row>
      <el-alert v-if="ragByType('correction') > 0" :title="`数据飞轮运转中: ${ragByType('correction')} 条人工修正已自动向量化, AI 审查时自动参考`" type="success" show-icon :closable="false" style="margin-top: 16px" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { agentApi } from '@/api/agent'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const userStore = useUserStore()
const alerts = ref<any>({})
const agents = ref<any[]>([])
const knowledgeItems = ref<any[]>([])
const knowledgeType = ref('laws')
const correctionStats = ref<any>({})
const testing = ref(false)
const saving = ref(false)
const showAIConfigDialog = ref(false)
const aiConfig = ref<any>({ base_url: '', model: '', has_key: false, status: 'unknown' })
const aiConfigForm = ref({ base_url: 'https://api.openai.com/v1', model: 'gpt-4-turbo-preview', api_key: '' })

// RAG 状态
const ragStats = ref<any>({})
const ragQuery = ref('')
const ragResults = ref<any[]>([])
const ragSearching = ref(false)
const ragSearched = ref(false)
const ragContractType = ref('')
const rebuilding = ref(false)

const isAdmin = computed(() => (userStore.userInfo as any)?.is_superuser || userStore.hasRole('admin'))
const learningRate = computed(() => {
  const total = correctionStats.value.total_corrections || 0
  const learned = correctionStats.value.learned || 0
  return total > 0 ? Math.round((learned / total) * 100) : 0
})

// RAG 辅助
const ragByType = (type: string) => ragStats.value.by_source?.find((s: any) => s.source_type === type)?.count || 0
const sourceLabel = (type: string) => ({ review_opinion: '审查意见', knowledge: '法律知识', correction: '人工修正' }[type] || type)
const riskLabel = (level: string) => ({ high: '高风险', medium: '中风险', low: '低风险', info: '提示' }[level] || level)
const riskTagType = (level: string) => ({ high: 'danger', medium: 'warning', low: 'info', info: 'info' }[level] || 'info')
const similarityTagType = (sim: number) => sim >= 0.8 ? 'success' : sim >= 0.65 ? 'warning' : 'info'

const refreshAlerts = async () => { try { alerts.value = await agentApi.getMonitoringAlerts() as any } catch { ElMessage.error('获取监控数据失败') } }
const loadAgents = async () => { try { const res: any = await agentApi.listAgents(); agents.value = res.agents || [] } catch {} }
const loadKnowledge = async () => {
  try {
    if (knowledgeType.value === 'laws') { const res: any = await agentApi.getLaws(); knowledgeItems.value = res.items || [] }
    else { const res: any = await agentApi.getCompliance(); knowledgeItems.value = res.items || [] }
  } catch { ElMessage.error('获取知识库失败') }
}
const initKnowledge = async () => { try { await agentApi.initKnowledge(); ElMessage.success('知识库初始化成功'); await loadKnowledge() } catch { ElMessage.error('初始化失败') } }
const loadStats = async () => { try { correctionStats.value = await agentApi.getCorrectionStats() } catch {} }
const loadAIConfig = async () => {
  try { const res: any = await agentApi.getAIConfig(); aiConfig.value = res; aiConfigForm.value.base_url = res.base_url || 'https://api.openai.com/v1'; aiConfigForm.value.model = res.model || 'gpt-4-turbo-preview' } catch {}
}
const testAIConnection = async () => {
  testing.value = true
  try { const res: any = await agentApi.testAIConnection(); if (res.status === 'ok') { ElMessage.success('AI连接测试成功'); aiConfig.value.status = 'ok' } else { ElMessage.error('AI连接测试失败: ' + (res.error || '')); aiConfig.value.status = 'error' } }
  catch { ElMessage.error('AI连接测试失败'); aiConfig.value.status = 'error' }
  finally { testing.value = false }
}
const saveAIConfig = async () => {
  saving.value = true
  try { await agentApi.updateAIConfig(aiConfigForm.value); ElMessage.success('AI配置保存成功'); showAIConfigDialog.value = false; loadAIConfig() }
  catch { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

// RAG 方法
const loadRagStats = async () => { try { ragStats.value = await agentApi.ragStats() as any } catch {} }
const searchRAG = async () => {
  if (!ragQuery.value.trim()) { ElMessage.warning('请输入检索文本'); return }
  ragSearching.value = true; ragSearched.value = true
  try { const res: any = await agentApi.ragSearch(ragQuery.value, ragContractType.value || undefined, 5); ragResults.value = res.results || [] }
  catch { ElMessage.error('RAG 检索失败'); ragResults.value = [] }
  finally { ragSearching.value = false }
}
const handleRebuild = async () => {
  try { await ElMessageBox.confirm('重建向量库将清空现有数据并重新向量化, 确认?', '警告', { type: 'warning' }) }
  catch { return }
  rebuilding.value = true
  try { const res: any = await agentApi.ragRebuild(); if (res.status === 'ok') { ElMessage.success('重建完成'); loadRagStats() } else { ElMessage.error('重建失败: ' + (res.error || '')) } }
  catch { ElMessage.error('重建失败') }
  finally { rebuilding.value = false }
}

onMounted(() => { refreshAlerts(); loadAgents(); loadKnowledge(); loadStats(); loadRagStats(); if (isAdmin.value) loadAIConfig() })
</script>

<style scoped>
.agent-dashboard { display: flex; flex-direction: column; gap: 20px; }
.section-card { width: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.agent-card { text-align: center; }
.agent-info { display: flex; align-items: center; gap: 12px; text-align: left; }
.agent-icon { font-size: 36px; }
.agent-info h4 { margin: 0 0 4px; font-size: 16px; }
.agent-info p { margin: 0; color: #666; font-size: 13px; }
.knowledge-content { white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6; color: #333; margin: 0; }
.rag-result-item { padding: 12px; border: 1px solid #ebeef5; border-radius: 4px; margin-bottom: 8px; }
.rag-result-header { margin-bottom: 6px; }
.rag-result-text { font-size: 13px; color: #333; margin: 4px 0; }
.rag-result-suggestion { font-size: 13px; color: #67c23a; margin: 4px 0; }
.rag-result-legal { font-size: 12px; color: #909399; margin: 4px 0; }
</style>
