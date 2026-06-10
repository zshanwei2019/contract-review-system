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
import { ElMessage } from 'element-plus'

const alerts = ref<any>({})
const agents = ref<any[]>([])
const knowledgeItems = ref<any[]>([])
const knowledgeType = ref('laws')
const correctionStats = ref<any>({})

const learningRate = computed(() => {
  const total = correctionStats.value.total_corrections || 0
  const learned = correctionStats.value.learned || 0
  return total > 0 ? Math.round((learned / total) * 100) : 0
})

const refreshAlerts = async () => {
  try {
    alerts.value = await agentApi.getMonitoringAlerts()
  } catch {
    ElMessage.error('获取监控数据失败')
  }
}

const loadAgents = async () => {
  try {
    const res = await agentApi.listAgents()
    agents.value = res.agents || []
  } catch {
    // ignore
  }
}

const loadKnowledge = async () => {
  try {
    if (knowledgeType.value === 'laws') {
      const res = await agentApi.getLaws()
      knowledgeItems.value = res.items || []
    } else {
      const res = await agentApi.getCompliance()
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
    loadKnowledge()
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

onMounted(() => {
  refreshAlerts()
  loadAgents()
  loadKnowledge()
  loadStats()
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
