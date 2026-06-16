<template>
  <div class="risk-items">
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>风险项列表</span>
          <div style="display: flex; gap: 8px;">
            <el-tag type="info" size="small">四维加权评估模型</el-tag>
            <el-button type="success" icon="Refresh" @click="handleInitItems" :loading="initLoading">初始化风险项</el-button>
          </div>
        </div>
      </template>
      
      <div class="search-bar">
        <el-select v-model="searchForm.risk_level" placeholder="风险等级" clearable style="width: 150px">
          <el-option label="高风险" value="high" />
          <el-option label="中风险" value="medium" />
          <el-option label="低风险" value="low" />
        </el-select>
        <el-select v-model="searchForm.is_resolved" placeholder="处理状态" clearable style="width: 150px">
          <el-option label="未处理" :value="false" />
          <el-option label="已处理" :value="true" />
        </el-select>
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
      </div>
      
      <el-table v-loading="loading" :data="items" stripe border @row-click="handleRowClick">
        <el-table-column prop="risk_level" label="风险等级" width="100">
          <template #default="{ row }">
            <el-tag :type="getRiskColor(row.risk_level)" size="small" effect="dark">
              {{ getRiskLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_description" label="风险描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="风险评分" width="200">
          <template #default="{ row }">
            <div v-if="row.risk_score != null" class="score-cell">
              <el-progress
                :percentage="row.risk_score"
                :color="getScoreColor(row.risk_score)"
                :stroke-width="10"
                :show-text="false"
                style="width: 100px; display: inline-block"
              />
              <span class="score-text" :style="{ color: getScoreColor(row.risk_score) }">
                {{ row.risk_score }}分
              </span>
            </div>
            <el-button v-else text type="primary" size="small" @click.stop="handleQuantify(row)">
              量化评估
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="四维评分" width="280">
          <template #default="{ row }">
            <div v-if="row.score_severity != null" class="dimension-scores">
              <div class="dim-item">
                <span class="dim-label">严重性</span>
                <el-progress :percentage="row.score_severity" :color="getScoreColor(row.score_severity)" :stroke-width="6" :show-text="false" style="width: 50px" />
                <span class="dim-value">{{ row.score_severity }}</span>
              </div>
              <div class="dim-item">
                <span class="dim-label">可能性</span>
                <el-progress :percentage="row.score_likelihood" :color="getScoreColor(row.score_likelihood)" :stroke-width="6" :show-text="false" style="width: 50px" />
                <span class="dim-value">{{ row.score_likelihood }}</span>
              </div>
              <div class="dim-item">
                <span class="dim-label">财务敞口</span>
                <el-progress :percentage="row.score_financial" :color="getScoreColor(row.score_financial)" :stroke-width="6" :show-text="false" style="width: 50px" />
                <span class="dim-value">{{ row.score_financial }}</span>
              </div>
              <div class="dim-item">
                <span class="dim-label">责任不对称</span>
                <el-progress :percentage="row.score_responsibility" :color="getScoreColor(row.score_responsibility)" :stroke-width="6" :show-text="false" style="width: 50px" />
                <span class="dim-value">{{ row.score_responsibility }}</span>
              </div>
            </div>
            <span v-else class="no-data">-</span>
          </template>
        </el-table-column>
        <el-table-column label="财务影响" width="160">
          <template #default="{ row }">
            <div v-if="row.potential_loss_max" class="financial-cell">
              <div class="loss-range">
                ¥{{ formatMoney(row.potential_loss_min) }} ~ ¥{{ formatMoney(row.potential_loss_max) }}
              </div>
              <div class="expected-loss">
                期望损失: <strong>¥{{ formatMoney(row.expected_loss) }}</strong>
              </div>
            </div>
            <span v-else class="no-data">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="clause_location" label="条款位置" width="140" show-overflow-tooltip />
        <el-table-column prop="is_resolved" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_resolved ? 'success' : 'warning'" size="small">
              {{ row.is_resolved ? '已处理' : '待处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click.stop="handleQuantify(row)">
              {{ row.risk_score != null ? '重新量化' : '量化评估' }}
            </el-button>
            <el-button
              v-if="!row.is_resolved"
              text
              type="success"
              size="small"
              @click.stop="handleResolve(row)"
            >
              标记处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          layout="total, prev, pager, next"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>

    <!-- 量化详情弹窗 -->
    <el-dialog v-model="detailVisible" title="风险量化评估详情" width="700px">
      <div v-if="currentItem" class="quantification-detail">
        <div class="detail-header">
          <el-tag :type="getRiskColor(currentItem.risk_level)" effect="dark" size="large">
            {{ getRiskLabel(currentItem.risk_level) }}
          </el-tag>
          <div class="overall-score">
            <span class="score-number" :style="{ color: getScoreColor(currentItem.risk_score || 0) }">
              {{ currentItem.risk_score || 0 }}
            </span>
            <span class="score-label">综合评分</span>
          </div>
        </div>

        <el-divider />

        <div class="dimensions-detail">
          <h4>📊 四维评分详情</h4>
          <div class="dim-grid">
            <div v-for="dim in dimensions" :key="dim.key" class="dim-card">
              <div class="dim-card-header">
                <span class="dim-card-label">{{ dim.label }}</span>
                <span class="dim-card-score" :style="{ color: getScoreColor(currentItem[dim.key] || 0) }">
                  {{ currentItem[dim.key] || 0 }}
                </span>
              </div>
              <el-progress
                :percentage="currentItem[dim.key] || 0"
                :color="getScoreColor(currentItem[dim.key] || 0)"
                :stroke-width="8"
              />
              <div class="dim-card-desc">{{ dim.description }}</div>
              <div class="dim-card-weight">权重: {{ dim.weight }}%</div>
            </div>
          </div>
        </div>

        <el-divider />

        <div class="financial-detail">
          <h4>💰 财务影响评估</h4>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="最小潜在损失">
              ¥{{ formatMoney(currentItem.potential_loss_min || 0) }}
            </el-descriptions-item>
            <el-descriptions-item label="最大潜在损失">
              ¥{{ formatMoney(currentItem.potential_loss_max || 0) }}
            </el-descriptions-item>
            <el-descriptions-item label="损失概率">
              {{ ((currentItem.loss_probability || 0) * 100).toFixed(0) }}%
            </el-descriptions-item>
            <el-descriptions-item label="期望损失">
              <strong>¥{{ formatMoney(currentItem.expected_loss || 0) }}</strong>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-if="currentItem.clause_text" class="clause-detail">
          <el-divider />
          <h4>📜 相关条款</h4>
          <div class="clause-location">
            📍 {{ currentItem.clause_location || '未知位置' }}
            <el-tag v-if="currentItem.confidence" size="small" type="info" style="margin-left: 8px">
              置信度: {{ (currentItem.confidence * 100).toFixed(0) }}%
            </el-tag>
          </div>
          <div class="clause-text-block">{{ currentItem.clause_text }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { risksApi } from '@/api/risks'
import { ElMessage, ElMessageBox } from 'element-plus'
const loading = ref(false)
const initLoading = ref(false)
const items = ref<any[]>([])
const searchForm = reactive({ risk_level: '', is_resolved: undefined as boolean | undefined })
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const detailVisible = ref(false)
const currentItem = ref<any>(null)

const dimensions = [
  { key: 'score_severity', label: '严重性', description: '风险发生后的损害程度', weight: 40 },
  { key: 'score_likelihood', label: '可能性', description: '风险发生的概率', weight: 25 },
  { key: 'score_financial', label: '财务风险敞口', description: '潜在经济损失规模', weight: 20 },
  { key: 'score_responsibility', label: '责任不对称性', description: '合同双方权利义务失衡程度', weight: 15 },
]

const getRiskColor = (level: string) => {
  const map: Record<string, string> = { high: 'danger', medium: 'warning', low: 'success', none: 'info' }
  return (map[level] || 'info') as any
}

const getRiskLabel = (level: string) => {
  const map: Record<string, string> = { high: '高风险', medium: '中风险', low: '低风险', none: '无风险' }
  return map[level] || level
}

const getScoreColor = (score: number) => {
  if (score >= 70) return '#F56C6C'
  if (score >= 40) return '#E6A23C'
  if (score >= 10) return '#67C23A'
  return '#909399'
}

const formatMoney = (amount: number) => {
  if (!amount) return '0'
  if (amount >= 10000) return (amount / 10000).toFixed(1) + '万'
  return amount.toLocaleString()
}

const fetchItems = async () => {
  loading.value = true
  try {
    const params: any = { page: pagination.page, page_size: pagination.page_size }
    if (searchForm.risk_level) params.risk_level = searchForm.risk_level
    if (searchForm.is_resolved !== undefined) params.is_resolved = searchForm.is_resolved
    const res: any = await risksApi.getItems(params)
    items.value = res.items || []
    pagination.total = res.total || 0
  } catch { ElMessage.error('获取风险项失败') } finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchItems() }

const handleRowClick = (row: any) => {
  currentItem.value = row
  detailVisible.value = true
}

const handleQuantify = async (row: any) => {
  try {
    ElMessage.info('正在进行量化评估...')
    const res: any = await risksApi.quantifyItem(row.id)
    const idx = items.value.findIndex(i => i.id === row.id)
    if (idx >= 0) items.value[idx] = res
    currentItem.value = res
    detailVisible.value = true
    ElMessage.success('量化评估完成')
  } catch { ElMessage.error('量化评估失败') }
}

const handleResolve = async (row: any) => {
  await ElMessageBox.confirm('确定标记该风险项为已处理？', '提示')
  try {
    await risksApi.updateItem(row.id, { is_resolved: true })
    ElMessage.success('已标记处理')
    fetchItems()
  } catch { ElMessage.error('操作失败') }
}

const handleInitItems = async () => {
  try {
    initLoading.value = true
    const res: any = await risksApi.initItems()
    ElMessage.success(res.message || '初始化成功')
    await fetchItems()
  } catch { ElMessage.error('初始化失败') } finally { initLoading.value = false }
}

onMounted(() => { fetchItems() })
</script>

<style scoped>
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }

.score-cell { display: flex; align-items: center; gap: 8px; }
.score-text { font-weight: bold; font-size: 14px; }

.dimension-scores { display: flex; flex-direction: column; gap: 4px; }
.dim-item { display: flex; align-items: center; gap: 6px; }
.dim-label { font-size: 11px; color: #666; width: 60px; }
.dim-value { font-size: 11px; font-weight: bold; width: 24px; text-align: right; }

.financial-cell { font-size: 12px; }
.loss-range { color: #F56C6C; font-weight: 500; }
.expected-loss { color: #666; margin-top: 4px; }
.expected-loss strong { color: #E6A23C; }
.no-data { color: #ccc; }

.quantification-detail { padding: 0 8px; }
.detail-header { display: flex; align-items: center; justify-content: space-between; }
.overall-score { text-align: center; }
.score-number { font-size: 48px; font-weight: bold; line-height: 1; }
.score-label { display: block; font-size: 12px; color: #999; margin-top: 4px; }

.dimensions-detail h4, .financial-detail h4, .clause-detail h4 { margin: 12px 0 8px; font-size: 14px; }

.dim-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.dim-card { background: #f8f9fa; border-radius: 8px; padding: 12px; }
.dim-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.dim-card-label { font-weight: 500; font-size: 13px; }
.dim-card-score { font-size: 20px; font-weight: bold; }
.dim-card-desc { font-size: 11px; color: #999; margin-top: 6px; }
.dim-card-weight { font-size: 11px; color: #67C23A; margin-top: 2px; }

.clause-location { display: flex; align-items: center; gap: 4px; color: #409EFF; font-size: 13px; margin-bottom: 8px; }
.clause-text-block { background: #f5f7fa; padding: 12px; border-radius: 6px; font-size: 13px; line-height: 1.6; border-left: 3px solid #409EFF; }
</style>
