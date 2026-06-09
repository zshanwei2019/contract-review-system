<template>
  <div class="dashboard">
    <!-- 欢迎区 -->
    <div class="welcome-section">
      <div class="welcome-text">
        <h2>{{ greeting }}，{{ userStore.userInfo?.name || '用户' }}</h2>
        <p>{{ currentDate }}</p>
      </div>
      <div class="quick-actions">
        <el-button type="primary" icon="Plus" @click="router.push('/contracts/create')">
          新建合同
        </el-button>
        <el-button icon="Search" @click="router.push('/reviews/list')">
          待审合同
        </el-button>
      </div>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">合同总数</div>
              <div class="stat-value">{{ stats.total_contracts || 0 }}</div>
            </div>
            <div class="stat-icon" style="background: #e6f7ff">
              <el-icon size="28" color="#1890ff"><Document /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">待审查</div>
              <div class="stat-value">{{ stats.pending_reviews || 0 }}</div>
            </div>
            <div class="stat-icon" style="background: #fff7e6">
              <el-icon size="28" color="#fa8c16"><Clock /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">审查中</div>
              <div class="stat-value">{{ stats.in_progress_reviews || 0 }}</div>
            </div>
            <div class="stat-icon" style="background: #f6ffed">
              <el-icon size="28" color="#52c41a"><Loading /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-label">未读通知</div>
              <div class="stat-value">{{ stats.unread_notifications || 0 }}</div>
            </div>
            <div class="stat-icon" style="background: #fff1f0">
              <el-icon size="28" color="#ff4d4f"><Bell /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 图表和列表 -->
    <el-row :gutter="20" class="content-row">
      <!-- 合同类型分布 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>合同类型分布</span>
            </div>
          </template>
          <div class="chart-container">
            <v-chart :option="typeChartOption" autoresize style="height: 300px" />
          </div>
        </el-card>
      </el-col>
      
      <!-- 月度趋势 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>月度合同趋势</span>
            </div>
          </template>
          <div class="chart-container">
            <v-chart :option="trendChartOption" autoresize style="height: 300px" />
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 最近合同 -->
    <el-card shadow="hover" class="recent-card">
      <template #header>
        <div class="card-header">
          <span>最近合同</span>
          <el-button text @click="router.push('/contracts/list')">查看全部</el-button>
        </div>
      </template>
      <el-table :data="stats.recent_contracts || []" stripe>
        <el-table-column prop="title" label="合同名称" min-width="200" />
        <el-table-column prop="contract_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ contractTypeLabels[row.contract_type] || row.contract_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="contractStatusColors[row.status]" size="small">
              {{ contractStatusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.risk_level" :type="getRiskColor(row.risk_level)" size="small">
              {{ row.risk_level }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/contracts/${row.id}`)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useUserStore } from '@/stores/user'
import { dashboardApi } from '@/api/dashboard'
import { contractTypeLabels, contractStatusLabels, contractStatusColors } from '@/types/contract'
import dayjs from 'dayjs'

use([CanvasRenderer, PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const router = useRouter()
const userStore = useUserStore()
const stats = ref<any>({})

const greeting = computed(() => {
  const hour = dayjs().hour()
  if (hour < 6) return '凌晨好'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 17) return '下午好'
  if (hour < 22) return '晚上好'
  return '夜深了'
})

const currentDate = computed(() => dayjs().format('YYYY年MM月DD日 dddd'))

const typeChartOption = computed(() => {
  const data = Object.entries(stats.value.type_distribution || {}).map(([key, value]) => ({
    name: contractTypeLabels[key as keyof typeof contractTypeLabels] || key,
    value,
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      labelLine: { show: false },
      data,
    }],
  }
})

const trendChartOption = computed(() => {
  const trend = stats.value.monthly_trend || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: trend.map((t: any) => t.month) },
    yAxis: { type: 'value' },
    series: [{
      data: trend.map((t: any) => t.count),
      type: 'bar',
      barWidth: '40%',
      itemStyle: { borderRadius: [4, 4, 0, 0], color: '#1890ff' },
    }],
  }
})

const getRiskColor = (level: string) => {
  const map: Record<string, string> = {
    high: 'danger',
    medium: 'warning',
    low: 'success',
  }
  return (map[level] || 'info') as any
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm')

onMounted(async () => {
  try {
    stats.value = await dashboardApi.getStats()
  } catch {}
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.welcome-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: #fff;
}

.welcome-text h2 {
  margin: 0 0 4px;
  font-size: 24px;
}

.welcome-text p {
  margin: 0;
  opacity: 0.8;
}

.quick-actions {
  display: flex;
  gap: 12px;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 8px;
}

.stat-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-info {
  flex: 1;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #1a1a1a;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.content-row {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  width: 100%;
}

.recent-card {
  margin-bottom: 24px;
}
</style>
