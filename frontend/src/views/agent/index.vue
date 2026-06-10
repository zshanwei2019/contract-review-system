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
      <el-alert
        v-if="alerts.summary"
        :title="alerts.summary"
        :type="alerts.total_alerts > 0 ? 'warning' : 'success'"
        show-icon
        :closable="false"
        style="margin-top: 16px"
      />
    </el-card>

    <!-- AI配置测试（仅管理员可见） -->
    <el-card v-if="isAdmin" shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span>⚙️ AI配置</span>
          <div>
            <el-button type="primary" @click="showAIConfigDialog = true">
              配置AI
            </el-button>
            <el-button @click="testAIConnection" :loading="testing">
              测试连接
            </el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="API地址">{{ aiConfig.base_url || '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ aiConfig.model || '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="API Key">{{ aiConfig.has_key ? '已配置' : '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="aiConfig.status === 'ok' ? 'success' : 'danger'">
            {{ aiConfig.status === 'ok' ? '正常' : '未连接' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- AI配置弹窗 -->
    <el-dialog v-model="showAIConfigDialog" title="AI配置" width="500px">
      <el-form :model="aiConfigForm" label-width="100px">
        <el-form-item label="API地址">
          <el-input v-model="aiConfigForm.base_url" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="aiConfigForm.model" placeholder="gpt-4-turbo-preview" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="aiConfigForm.api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAIConfigDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAIConfig" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- Agent列表 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <span>🤖 AI审查Agent</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="8" v-for="agent in agents" :key="agent.id">
          <el-card shadow="never" class="agent-card">
            <div class="agent-info">
              <span class="agent-icon">{{ agent.icon }}</span>
              <div>
                <h4>{{ agent.name }}</h4>
                <p>{{ agent.focus }}</p>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
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
        <span>📈 反馈学习统计</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="总修正数" :value="correctionStats.total_corrections || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已学习" :value="correctionStats.learned || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="待学习" :value="correctionStats.pending || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="学习率" :value="learningRate" suffix="%" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { agentApi } from '@/api/agent'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()

const alerts = ref<any>({})
const agents = ref<any[]>([])
const knowledgeItems = ref<any[]>([])
const knowledgeType = ref('laws')
const correctionStats = ref<any>({})
const testing = ref(false)
const saving = ref(false)
const showAIConfigDialog = ref(false)
const aiConfig = ref<any>({
  base_url: '',
  model: '',
  has_key: false,
  status: 'unknown'
})
const aiConfigForm = ref({
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4-turbo-preview',
  api_key: ''
})

// 检查是否为管理员
const isAdmin = computed(() => {
  return (userStore.userInfo as any)?.is_superuser || userStore.hasRole('admin')
})

const learningRate = computed(() => {
  const total = correctionStats.value.total_corrections || 0
  const learned = correctionStats.value.learned || 0
  return total > 0 ? Math.round((learned / total) * 100) : 0
})

const refreshAlerts = async () => {
  try {
    alerts.value = await agentApi.getMonitoringAlerts() as any
  } catch {
    ElMessage.error('获取监控数据失败')
  }
}

const loadAgents = async () => {
  try {
    const res: any = await agentApi.listAgents()
    agents.value = res.agents || []
  } catch {
    // ignore
  }
}

const loadKnowledge = async () => {
  try {
    if (knowledgeType.value === 'laws') {
      const res: any = await agentApi.getLaws()
      knowledgeItems.value = res.items || []
    } else {
      const res: any = await agentApi.getCompliance()
      knowledgeItems.value = res.items || []
    }
  } catch {
    ElMessage.error('获取知识库失败')
  }
}

const initKnowledge = async () => {
  try {
    await agentApi.initKnowledge()
    ElMessage.success('知识库初始化成功')
    await loadKnowledge()
  } catch {
    ElMessage.error('初始化失败')
  }
}

const loadStats = async () => {
  try {
    correctionStats.value = await agentApi.getCorrectionStats()
  } catch {
    // ignore
  }
}

const loadAIConfig = async () => {
  try {
    const res: any = await agentApi.getAIConfig()
    aiConfig.value = res
    aiConfigForm.value.base_url = res.base_url || 'https://api.openai.com/v1'
    aiConfigForm.value.model = res.model || 'gpt-4-turbo-preview'
  } catch {
    // ignore
  }
}

const testAIConnection = async () => {
  testing.value = true
  try {
    const res: any = await agentApi.testAIConnection()
    if (res.status === 'ok') {
      ElMessage.success('AI连接测试成功')
      aiConfig.value.status = 'ok'
    } else {
      ElMessage.error('AI连接测试失败: ' + (res.error || '未知错误'))
      aiConfig.value.status = 'error'
    }
  } catch (error: any) {
    ElMessage.error('AI连接测试失败: ' + (error.message || '网络错误'))
    aiConfig.value.status = 'error'
  } finally {
    testing.value = false
  }
}

const saveAIConfig = async () => {
  saving.value = true
  try {
    await agentApi.updateAIConfig(aiConfigForm.value)
    ElMessage.success('AI配置保存成功')
    showAIConfigDialog.value = false
    loadAIConfig()
  } catch (error: any) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  refreshAlerts()
  loadAgents()
  loadKnowledge()
  loadStats()
  if (isAdmin.value) {
    loadAIConfig()
  }
})
</script>

<style scoped>
.agent-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-card {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.agent-card {
  text-align: center;
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
}

.agent-icon {
  font-size: 36px;
}

.agent-info h4 {
  margin: 0 0 4px;
  font-size: 16px;
}

.agent-info p {
  margin: 0;
  color: #666;
  font-size: 13px;
}

.knowledge-content {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  margin: 0;
}
</style>
