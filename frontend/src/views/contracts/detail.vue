<template>
  <div class="contract-detail" v-loading="loading">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button icon="Back" @click="router.back()">返回</el-button>
            <span class="title">合同详情</span>
            <el-tag :type="contractStatusColors[contract.status as ContractStatus] as any" size="large">
              {{ contractStatusLabels[contract.status as ContractStatus] }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button
              v-if="contract.status === 'draft'"
              type="success"
              icon="Check"
              @click="handleSubmit"
            >
              提交审查
            </el-button>
            <el-button
              v-if="canReview"
              type="primary"
              icon="Search"
              @click="handleReview"
            >
              开始审查
            </el-button>
            <el-button
              type="warning"
              icon="MagicStick"
              :loading="aiReviewing"
              @click="handleAiReview"
            >
              AI智能审查
            </el-button>
            <el-dropdown trigger="click" @command="handleAgentReview">
              <el-button type="primary" plain icon="Connection">
                多Agent审查 <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="all">全部Agent</el-dropdown-item>
                  <el-dropdown-item command="legal">⚖️ 法务审查</el-dropdown-item>
                  <el-dropdown-item command="finance">💰 财务审查</el-dropdown-item>
                  <el-dropdown-item command="business">📋 业务审查</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button
              v-if="contract.risk_level"
              type="success"
              icon="MagicStick"
              :loading="modificationLoading"
              @click="handleGetModifications"
            >
              AI修改建议
            </el-button>
            <el-dropdown trigger="click" @command="handleExportModified">
              <el-button type="primary" plain icon="Download">
                导出合同 <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item disabled>修改版 (含批注)</el-dropdown-item>
                  <el-dropdown-item command="word-modified">📄 Word - 修改版</el-dropdown-item>
                  <el-dropdown-item command="pdf-modified">📕 PDF - 修改版</el-dropdown-item>
                  <el-dropdown-item command="markdown-modified">📝 Markdown - 修改版</el-dropdown-item>
                  <el-dropdown-item divided disabled>清洁版 (无痕迹)</el-dropdown-item>
                  <el-dropdown-item command="word-clean">📄 Word - 清洁版</el-dropdown-item>
                  <el-dropdown-item command="pdf-clean">📕 PDF - 清洁版</el-dropdown-item>
                  <el-dropdown-item divided disabled>原文版</el-dropdown-item>
                  <el-dropdown-item command="word-original">📄 Word - 原文版</el-dropdown-item>
                  <el-dropdown-item command="pdf-original">📕 PDF - 原文版</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button
              type="info"
              icon="Document"
              :loading="compareLoading"
              @click="handleCompare"
            >
              原文对比
            </el-button>
            <el-button
              v-if="contract.status === 'reviewed' || contract.status === 'draft'"
              type="warning"
              plain
              icon="Promotion"
              @click="showApprovalDialog = true"
            >
              发起审批
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 基本信息 -->
      <el-descriptions :column="3" border class="info-section" size="large">
        <el-descriptions-item label="合同编号" :span="1">{{ contract.contract_no }}</el-descriptions-item>
        <el-descriptions-item label="合同类型" :span="1">
          <el-tag size="small" type="primary">{{ contractTypeLabels[contract.contract_type as ContractType] || contract.contract_type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="合同状态" :span="1">
          <el-tag :type="contractStatusColors[contract.status as ContractStatus] as any" size="small">
            {{ contractStatusLabels[contract.status as ContractStatus] }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="甲方" :span="1">{{ contract.party_a || '-' }}</el-descriptions-item>
        <el-descriptions-item label="乙方" :span="1">{{ contract.party_b || '-' }}</el-descriptions-item>
        <el-descriptions-item label="合同金额" :span="1">
          <span style="color: #f56c6c; font-weight: 600; font-size: 16px;">
            {{ contract.amount ? formatAmount(contract.amount) : '-' }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="签订日期" :span="1">{{ contract.sign_date ? String(contract.sign_date).substring(0, 10) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="生效日期" :span="1">{{ contract.effective_date ? String(contract.effective_date).substring(0, 10) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期" :span="1">{{ contract.expiry_date ? String(contract.expiry_date).substring(0, 10) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="所属部门" :span="1">{{ contract.department || '-' }}</el-descriptions-item>
        <el-descriptions-item label="币种" :span="1">{{ contract.currency || 'CNY' }}</el-descriptions-item>
        <el-descriptions-item label="项目名称" :span="1">{{ contract.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="合同描述" :span="3">
          <div style="white-space: pre-wrap; line-height: 1.6;">{{ contract.description || '-' }}</div>
        </el-descriptions-item>
      </el-descriptions>
      
      <!-- 风险信息 -->
      <div v-if="contract.risk_level" class="risk-section">
        <h3 style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 20px;">⚠️</span> 风险评估
        </h3>
        <el-row :gutter="24">
          <el-col :span="8">
            <div class="risk-card">
              <div class="risk-label">风险等级</div>
              <el-tag :type="getRiskColor(contract.risk_level)" size="large" effect="dark">
                {{ getRiskLabel(contract.risk_level) }}
              </el-tag>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="risk-card">
              <div class="risk-label">风险评分</div>
              <div class="risk-score">
                <span class="score-value" :style="{ color: contract.risk_score > 70 ? '#f56c6c' : contract.risk_score > 40 ? '#e6a23c' : '#67c23a' }">
                  {{ contract.risk_score || 0 }}
                </span>
                <span class="score-unit">/ 100</span>
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="risk-card">
              <div class="risk-label">审查时间</div>
              <div class="risk-time">{{ contract.reviewed_at ? formatDate(contract.reviewed_at) : '-' }}</div>
            </div>
          </el-col>
        </el-row>
      </div>
      
      <!-- 风险量化汇总 -->
      <div class="risk-quantification-section">
        <h3>📊 风险量化评估</h3>
        <div v-if="riskSummary" class="risk-summary">
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="summary-card" :class="riskSummary.overall_level">
                <div class="summary-number">{{ riskSummary.overall_score }}</div>
                <div class="summary-label">综合评分</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-card high">
                <div class="summary-number">{{ riskSummary.high_risks }}</div>
                <div class="summary-label">高风险项</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-card medium">
                <div class="summary-number">{{ riskSummary.medium_risks }}</div>
                <div class="summary-label">中风险项</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-card loss">
                <div class="summary-number">¥{{ formatMoney(riskSummary.total_expected_loss) }}</div>
                <div class="summary-label">总期望损失</div>
              </div>
            </el-col>
          </el-row>
          <div class="summary-actions">
            <el-button type="primary" size="small" @click="handleQuantifyAll">批量量化评估</el-button>
            <el-button size="small" @click="router.push('/risks/items')">查看全部风险项</el-button>
          </div>
        </div>
        <el-empty v-else description="暂无风险量化数据">
          <el-button type="primary" @click="handleQuantifyAll">开始量化评估</el-button>
        </el-empty>
      </div>

      <!-- 审查记录 -->
      <div class="review-section">
        <h3>审查记录</h3>
        <el-timeline v-if="reviews.length > 0">
          <el-timeline-item
            v-for="review in reviews"
            :key="review.id"
            :timestamp="formatDate(review.created_at)"
            placement="top"
          >
            <el-card shadow="never">
              <div class="review-item">
                <div class="review-header">
                  <el-tag :type="getReviewStatusColor(review.status)" size="small">
                    {{ reviewStatusLabels[review.status] }}
                  </el-tag>
                  <span class="reviewer">审查人：{{ review.reviewer?.name || '-' }}</span>
                </div>
                <p v-if="review.summary" class="review-summary">{{ review.summary }}</p>
                <el-button text type="primary" @click="router.push(`/reviews/${review.id}`)">
                  查看详情
                </el-button>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无审查记录" />
      </div>
      
      <!-- 版本历史 -->
      <div class="version-section">
        <h3>版本历史</h3>
        <el-table v-if="versions.length > 0" :data="versions" border>
          <el-table-column prop="version_no" label="版本号" width="100" />
          <el-table-column prop="description" label="变更说明" min-width="200" />
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无版本记录" />
      </div>

      <!-- 🔬 高级AI分析 -->
      <div class="advanced-section">
        <h3>🔬 高级AI分析</h3>
        <el-tabs v-model="advancedTab" type="border-card">
          <el-tab-pane label="📋 条款审查" name="clauses">
            <div v-if="clauseReviewData" class="tab-content">
              <el-row :gutter="16" style="margin-bottom: 16px;">
                <el-col :span="6">
                  <el-statistic title="条款数" :value="clauseReviewData.summary?.total_clauses || 0" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="建议数" :value="clauseReviewData.summary?.total_suggestions || 0" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="AI调用" :value="clauseReviewData.ai_calls_made || 0" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="节省调用" :value="clauseReviewData.ai_calls_saved || 0" />
                </el-col>
              </el-row>
              <el-collapse v-if="clauseReviewData.clause_reviews?.length">
                <el-collapse-item
                  v-for="cr in clauseReviewData.clause_reviews"
                  :key="cr.clause_index"
                  :title="`${cr.clause_title || '条款 ' + cr.clause_index} — 风险: ${cr.risk_level || '无'} (${cr.risk_score || 0}分)`"
                >
                  <p><strong>内容:</strong> {{ cr.clause_content?.substring(0, 200) }}</p>
                  <div v-if="cr.findings?.length">
                    <p><strong>发现:</strong></p>
                    <ul>
                      <li v-for="(f, i) in cr.findings" :key="i">
                        <el-tag :type="f.severity === 'high' ? 'danger' : f.severity === 'medium' ? 'warning' : 'info'" size="small">{{ f.severity }}</el-tag>
                        {{ f.description }}
                      </li>
                    </ul>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <el-empty v-else description="暂无条款审查数据" />
            </div>
            <div v-else-if="clauseReviewLoading" style="text-align:center;padding:40px;">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <p>正在审查...</p>
            </div>
            <div v-else style="text-align:center;padding:20px;">
              <el-button type="primary" :loading="clauseReviewLoading" @click="loadClauseReview">开始条款级审查</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="📝 义务清单" name="obligations">
            <div v-if="obligationsData" class="tab-content">
              <el-row :gutter="16" style="margin-bottom: 16px;">
                <el-col :span="8">
                  <el-statistic title="总义务数" :value="obligationsData.summary?.total_obligations || 0" />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="甲方义务" :value="obligationsData.summary?.party_a_count || 0" />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="乙方义务" :value="obligationsData.summary?.party_b_count || 0" />
                </el-col>
              </el-row>
              <el-table v-if="obligationsData.obligations?.length" :data="obligationsData.obligations" border>
                <el-table-column prop="type" label="类型" width="100">
                  <template #default="{ row }">
                    <el-tag size="small">{{ obligationTypeLabels[row.type] || row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="party" label="义务方" width="100" />
                <el-table-column prop="action" label="义务内容" min-width="250" show-overflow-tooltip />
                <el-table-column prop="deadline" label="截止日期" width="120" />
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'pending' ? 'warning' : row.status === 'completed' ? 'success' : 'info'" size="small">
                      {{ obligationStatusLabels[row.status] || row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="未提取到义务" />
            </div>
            <div v-else-if="obligationsLoading" style="text-align:center;padding:40px;">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <p>正在提取义务...</p>
            </div>
            <div v-else style="text-align:center;padding:20px;">
              <el-button type="primary" :loading="obligationsLoading" @click="loadObligations">提取义务清单</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="🎯 谈判策略" name="playbook">
            <div v-if="playbookData" class="tab-content">
              <el-row :gutter="16" style="margin-bottom: 16px;">
                <el-col :span="8">
                  <el-statistic title="策略项数" :value="playbookData.summary?.total_items || 0" />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="底线条款" :value="playbookData.summary?.insist_count || 0" />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="可协商" :value="playbookData.summary?.negotiable_count || 0" />
                </el-col>
              </el-row>
              <el-timeline v-if="playbookData.strategies?.length">
                <el-timeline-item
                  v-for="(s, i) in playbookData.strategies"
                  :key="i"
                  :color="stanceColors[s.stance] || '#909399'"
                  :timestamp="`第${i+1}步`"
                >
                  <el-card shadow="hover">
                    <template #header>
                      <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span><el-tag :type="stanceTagTypes[s.stance]" size="small">{{ stanceLabels[s.stance] || s.stance }}</el-tag> {{ s.clause_title }}</span>
                      </div>
                    </template>
                    <p><strong>底线:</strong> {{ s.bottom_line }}</p>
                    <p><strong>话术:</strong> {{ s.talking_point }}</p>
                    <p v-if="s.fallback"><strong>次选方案:</strong> {{ s.fallback }}</p>
                    <p v-if="s.trade_item"><strong>交换条件:</strong> {{ s.trade_item }}</p>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else description="暂无谈判策略" />
            </div>
            <div v-else-if="playbookLoading" style="text-align:center;padding:40px;">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <p>正在生成策略...</p>
            </div>
            <div v-else style="text-align:center;padding:20px;">
              <el-button type="primary" :loading="playbookLoading" @click="loadPlaybook">生成谈判策略</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="👤 相对方画像" name="party">
            <div v-if="partyProfileData" class="tab-content">
              <el-row :gutter="16" style="margin-bottom: 16px;">
                <el-col :span="6">
                  <el-statistic title="风险等级">
                    <template #default>
                      <el-tag :type="riskTierColors[partyProfileData.risk_tier]" size="large">
                        {{ riskTierLabels[partyProfileData.risk_tier] || partyProfileData.risk_tier }}
                      </el-tag>
                    </template>
                  </el-statistic>
                </el-col>
                <el-col :span="6">
                  <el-statistic title="谈判风格" :value="partyProfileData.negotiation_style || '-'" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="风险趋势" :value="partyProfileData.risk_trend || '-'" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="历史合同" :value="partyProfileData.total_contracts || 0" />
                </el-col>
              </el-row>
              <div v-if="partyProfileData.recommendations?.length" style="margin-top:16px;">
                <h4>建议</h4>
                <ul>
                  <li v-for="(r, i) in partyProfileData.recommendations" :key="i">{{ r }}</li>
                </ul>
              </div>
              <div v-if="partyProfileData.risk_patterns?.length" style="margin-top:16px;">
                <h4>风险模式</h4>
                <el-tag v-for="(p, i) in partyProfileData.risk_patterns" :key="i" style="margin:2px;">{{ p }}</el-tag>
              </div>
            </div>
            <div v-else-if="partyProfileLoading" style="text-align:center;padding:40px;">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <p>正在分析...</p>
            </div>
            <div v-else style="text-align:center;padding:20px;">
              <el-button v-if="contract.party_b" type="primary" :loading="partyProfileLoading" @click="loadPartyProfile">分析 {{ contract.party_b }}</el-button>
              <el-empty v-else description="未填写乙方信息" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="⚖️ 合规检查" name="compliance">
            <div v-if="complianceData" class="tab-content">
              <el-alert
                :title="`合规风险: ${complianceData.summary?.overall_risk || '无'}`"
                :type="complianceData.summary?.overall_risk === 'high' ? 'error' : complianceData.summary?.overall_risk === 'medium' ? 'warning' : 'success'"
                :closable="false" show-icon style="margin-bottom:16px;"
              />
              <el-row :gutter="16" style="margin-bottom: 16px;">
                <el-col :span="8">
                  <el-statistic title="问题总数" :value="complianceData.summary?.total_issues || 0" />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="高风险" :value="complianceData.summary?.risk_distribution?.high || 0" />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="中风险" :value="complianceData.summary?.risk_distribution?.medium || 0" />
                </el-col>
              </el-row>
              <el-table v-if="complianceData.issues?.length" :data="complianceData.issues" border>
                <el-table-column label="严重性" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.severity === 'high' ? 'danger' : 'warning'" size="small">{{ row.severity }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="type" label="类型" width="160" />
                <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
                <el-table-column prop="regulation" label="法规依据" width="200" show-overflow-tooltip />
                <el-table-column prop="suggestion" label="建议" min-width="200" show-overflow-tooltip />
              </el-table>
              <el-empty v-else description="未发现合规问题" />
            </div>
            <div v-else-if="complianceLoading" style="text-align:center;padding:40px;">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <p>正在检查...</p>
            </div>
            <div v-else style="text-align:center;padding:20px;">
              <el-button type="primary" :loading="complianceLoading" @click="loadCompliance">合规性检查</el-button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-card>
    
    <!-- AI审查结果对话框 -->
    <el-dialog v-model="showAiResult" title="AI智能审查结果" width="700px">
      <div v-if="aiResult.risk_level">
        <el-alert
          :title="'风险等级: ' + getRiskLabel(aiResult.risk_level)"
          :description="aiResult.summary"
          :type="aiResult.risk_level === 'high' ? 'error' : aiResult.risk_level === 'medium' ? 'warning' : 'success'"
          show-icon
          :closable="false"
          style="margin-bottom: 20px"
        />
        
        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="12">
            <el-statistic title="风险评分" :value="aiResult.risk_score" suffix="/ 100" />
          </el-col>
          <el-col :span="12">
            <el-statistic title="发现项数" :value="aiResult.findings_count" suffix="项" />
          </el-col>
        </el-row>
        
        <p style="color: #666; margin: 0;">
          审查意见已自动生成，可在「审查记录」中查看详细内容。
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="router.push(`/reviews/${aiResult.review_task_id}`)">
          查看审查详情
        </el-button>
        <el-button @click="showAiResult = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 修改建议对话框 -->
    <el-dialog
      v-model="showModificationDialog"
      title="AI修改建议"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-if="modificationSuggestions.length === 0" style="text-align: center; padding: 40px;">
        <el-empty description="暂无修改建议" />
      </div>
      <div v-else>
        <el-alert
          :title="`共 ${modificationSuggestions.length} 个修改建议`"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        />
        <el-table
          :data="modificationSuggestions"
          border
          style="width: 100%"
          @selection-change="(val: any[]) => selectedSuggestions = val.map((v: any) => v.id)"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column label="条款" prop="clause" width="120" />
          <el-table-column label="优先级" width="100">
            <template #default="{ row }">
              <el-tag :type="getPriorityType(row.priority)">
                {{ getPriorityLabel(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="修改理由" prop="reason" min-width="200" show-overflow-tooltip />
          <el-table-column label="法律依据" prop="legal_basis" min-width="150" show-overflow-tooltip />
        </el-table>
        <div style="margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 4px;">
          <p style="margin: 0 0 8px; font-weight: 600;">📝 详细修改建议：</p>
          <div v-for="item in modificationSuggestions" :key="item.id" style="margin-bottom: 12px;">
            <p style="margin: 0 0 4px; color: #409eff; font-weight: 500;">{{ item.clause }}：</p>
            <p style="margin: 0 0 4px; color: #666;">{{ item.reason }}</p>
            <p style="margin: 0; color: #e6a23c;">⚠️ {{ item.risk_if_not_modified }}</p>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showModificationDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="applyingModifications"
          :disabled="selectedSuggestions.length === 0"
          @click="handleApplyModifications"
        >
          应用选中的修改建议 ({{ selectedSuggestions.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- 修改后合同内容对话框 -->
    <el-dialog
      v-model="showModifiedContent"
      title="修改后合同"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-if="diffSummary" style="margin-bottom: 16px;">
        <el-alert
          title="修改摘要"
          :description="diffSummary"
          type="success"
          :closable="false"
          show-icon
        />
      </div>
      <div style="margin-bottom: 16px; display: flex; gap: 8px;">
        <el-button type="primary" icon="Download" @click="handleExportModified('word-modified')">
          导出Word
        </el-button>
        <el-button type="warning" icon="Download" @click="handleExportModified('pdf-modified')">
          导出PDF
        </el-button>
        <el-button type="info" icon="Download" @click="handleExportModified('markdown-modified')">
          导出Markdown
        </el-button>
      </div>
      <div style="max-height: 500px; overflow-y: auto; padding: 16px; background: #f5f7fa; border-radius: 4px;">
        <div v-html="renderMarkdown(modifiedContent)"></div>
      </div>
      <template #footer>
        <el-button @click="showModifiedContent = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 原文对比对话框 -->
    <el-dialog
      v-model="showCompareDialog"
      title="原文对比"
      width="95%"
      :close-on-click-modal="false"
      fullscreen
    >
      <div v-if="compareLoading" style="text-align: center; padding: 40px;">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p>正在生成对比...</p>
      </div>
      <div v-else-if="compareData">
        <el-alert
          :title="`合同: ${compareData.contract_title}`"
          :description="compareData.has_modifications ? '已显示原合同与修改后合同的对比' : '该合同尚未进行AI修改'"
          :type="compareData.has_modifications ? 'success' : 'info'"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        />
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="compare-panel">
              <div class="compare-header">
                <el-tag type="info" size="large">📄 原合同</el-tag>
              </div>
              <div class="compare-content">
                <div v-html="renderMarkdown(compareData.original_content)"></div>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="compare-panel">
              <div class="compare-header">
                <el-tag type="success" size="large">✨ 修改后合同</el-tag>
                <el-tag v-if="compareData.version_no" type="warning" size="small" style="margin-left: 8px;">
                  版本 {{ compareData.version_no }}
                </el-tag>
              </div>
              <div class="compare-content">
                <div v-if="compareData.modified_content" v-html="renderMarkdown(compareData.modified_content)"></div>
                <el-empty v-else description="暂无修改内容" />
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="showCompareDialog = false">关闭</el-button>
        <el-button type="primary" @click="exportCompare('markdown')" :disabled="!compareData?.has_modifications">
          <el-icon><Download /></el-icon> 导出Markdown
        </el-button>
        <el-button type="success" @click="exportCompare('word')" :disabled="!compareData?.has_modifications">
          <el-icon><Document /></el-icon> 导出Word
        </el-button>
      </template>
    </el-dialog>

    <!-- 发起审批弹窗 -->
    <el-dialog v-model="showApprovalDialog" title="发起审批流程" width="500px">
      <el-form label-width="100px">
        <el-form-item label="合同名称">
          <span>{{ contract.title }}</span>
        </el-form-item>
        <el-form-item label="审批流程">
          <el-select v-model="selectedWorkflowId" placeholder="选择审批流程" style="width: 100%">
            <el-option
              v-for="wf in availableWorkflows"
              :key="wf.id"
              :label="wf.name + (wf.contract_type ? ` (${wf.contract_type})` : ' (通用)')"
              :value="wf.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showApprovalDialog = false">取消</el-button>
        <el-button type="primary" :loading="launchingApproval" @click="handleLaunchApproval">发起</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'
import { reviewsApi } from '@/api/reviews'
import { risksApi } from '@/api/risks'
import { advancedApi } from '@/api/advanced'
import { workflowsApi } from '@/api/workflows'
import { contractTypeLabels, contractStatusLabels, contractStatusColors } from '@/types/contract'
import type { ContractType, ContractStatus } from '@/types/contract'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const aiReviewing = ref(false)
const aiResult = ref<any>({})
const showAiResult = ref(false)
const contract = ref<any>({})
const reviews = ref<any[]>([])
const versions = ref<any[]>([])
const riskSummary = ref<any>(null)
const quantifyLoading = ref(false)
const compareLoading = ref(false)
const showCompareDialog = ref(false)
const compareData = ref<any>(null)
const modificationLoading = ref(false)
const modifiedContent = ref('')
const showModifiedContent = ref(false)
const modificationSuggestions = ref<any[]>([])

// 审批工作流
const showApprovalDialog = ref(false)
const workflowDefinitions = ref<any[]>([])
const selectedWorkflowId = ref<number | null>(null)
const launchingApproval = ref(false)

const availableWorkflows = computed(() => workflowDefinitions.value)
const selectedSuggestions = ref<number[]>([])
const showModificationDialog = ref(false)
const applyingModifications = ref(false)
const diffSummary = ref('')

// ========== 高级AI分析 ==========
const advancedTab = ref('clauses')
const clauseReviewLoading = ref(false)
const clauseReviewData = ref<any>(null)
const obligationsLoading = ref(false)
const obligationsData = ref<any>(null)
const playbookLoading = ref(false)
const playbookData = ref<any>(null)
const partyProfileLoading = ref(false)
const partyProfileData = ref<any>(null)
const complianceLoading = ref(false)
const complianceData = ref<any>(null)

const obligationTypeLabels: Record<string, string> = {
  payment: '付款', delivery: '交付', notice: '通知',
  confidentiality: '保密', non_compete: '竞业', insurance: '保险',
  maintenance: '维护', report: '报告', other: '其他',
}
const obligationStatusLabels: Record<string, string> = {
  pending: '待履行', in_progress: '履行中', completed: '已完成', overdue: '已逾期',
}
const stanceLabels: Record<string, string> = {
  INSIST: '必须坚持', PUSH_BACK: '坚决反对', NEGOTIATE: '重点谈判',
  COMPROMISE: '可妥协', ACCEPT: '可接受',
}
const stanceTagTypes: Record<string, string> = {
  INSIST: 'danger', PUSH_BACK: 'danger', NEGOTIATE: 'warning',
  COMPROMISE: 'info', ACCEPT: 'success',
}
const stanceColors: Record<string, string> = {
  INSIST: '#f56c6c', PUSH_BACK: '#e6a23c', NEGOTIATE: '#409eff',
  COMPROMISE: '#909399', ACCEPT: '#67c23a',
}
const riskTierLabels: Record<string, string> = {
  LOW: '低风险', MODERATE: '中等风险', ELEVATED: '较高风险', HIGH: '高风险', UNKNOWN: '未知',
}
const riskTierColors: Record<string, string> = {
  LOW: 'success', MODERATE: 'info', ELEVATED: 'warning', HIGH: 'danger', UNKNOWN: 'info',
}

const loadClauseReview = async () => {
  clauseReviewLoading.value = true
  try {
    clauseReviewData.value = await advancedApi.clauseReview(contractId.value)
    ElMessage.success('条款审查完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '条款审查失败')
  } finally {
    clauseReviewLoading.value = false
  }
}

const loadObligations = async () => {
  obligationsLoading.value = true
  try {
    obligationsData.value = await advancedApi.getObligations(contractId.value)
    ElMessage.success('义务提取完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '义务提取失败')
  } finally {
    obligationsLoading.value = false
  }
}

const loadPlaybook = async () => {
  playbookLoading.value = true
  try {
    playbookData.value = await advancedApi.getPlaybook(contractId.value)
    ElMessage.success('策略生成完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '策略生成失败')
  } finally {
    playbookLoading.value = false
  }
}

const loadPartyProfile = async () => {
  if (!contract.value.party_b) return
  partyProfileLoading.value = true
  try {
    partyProfileData.value = await advancedApi.getPartyProfile(contract.value.party_b)
    ElMessage.success('画像分析完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '画像分析失败')
  } finally {
    partyProfileLoading.value = false
  }
}

const loadCompliance = async () => {
  complianceLoading.value = true
  try {
    complianceData.value = await advancedApi.complianceCheckByContract(contractId.value)
    ElMessage.success('合规检查完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '合规检查失败')
  } finally {
    complianceLoading.value = false
  }
}

const contractId = computed(() => Number(route.params.id))

const canReview = computed(() => {
  return ['pending_review', 'reviewing'].includes(contract.value.status)
})

const fetchContract = async () => {
  loading.value = true
  try {
    contract.value = await contractsApi.get(contractId.value)
    const [reviewsRes, versionsRes] = await Promise.all([
      reviewsApi.list({ contract_id: contractId.value }),
      contractsApi.getVersions(contractId.value),
    ])
    reviews.value = reviewsRes.items || []
    versions.value = versionsRes || []
    // 获取风险量化汇总
    try {
      riskSummary.value = await risksApi.getContractRiskSummary(contractId.value)
    } catch { /* 暂无风险数据 */ }
  } catch {
    ElMessage.error('获取合同详情失败')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  await ElMessageBox.confirm('确定提交该合同审查？', '提示', { type: 'warning' })
  try {
    await contractsApi.submit(contractId.value as any)
    ElMessage.success('提交成功')
    fetchContract()
  } catch {
    ElMessage.error('提交失败')
  }
}

const formatMoney = (amount: number) => {
  if (!amount) return '0'
  if (amount >= 10000) return (amount / 10000).toFixed(1) + '万'
  return amount.toLocaleString()
}

const handleQuantifyAll = async () => {
  try {
    await risksApi.quantifyAllRisks(contractId.value)
    riskSummary.value = await risksApi.getContractRiskSummary(contractId.value)
    ElMessage.success('量化评估完成')
  } catch { ElMessage.error('量化评估失败') }
}

const handleReview = () => {
  router.push(`/reviews/list?contract_id=${contractId.value}`)
}

const handleAiReview = async () => {
  try {
    await ElMessageBox.confirm(
      'AI将对合同进行智能风险审查，是否继续？',
      'AI智能审查',
      { confirmButtonText: '开始审查', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  
  aiReviewing.value = true
  try {
    const result: any = await contractsApi.aiReview(contractId.value)
    aiResult.value = result
    showAiResult.value = true
    ElMessage.success('AI审查完成')
    fetchContract()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI审查失败，请稍后重试')
  } finally {
    aiReviewing.value = false
  }
}

const handleAgentReview = async (command: string) => {
  const agents = command === 'all' ? undefined : [command]
  const label = command === 'all' ? '全部Agent' : { legal: '法务', finance: '财务', business: '业务' }[command]
  
  try {
    await ElMessageBox.confirm(
      `将使用${label}Agent对合同进行协作审查，是否继续？`,
      '多Agent审查',
      { confirmButtonText: '开始', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  
  aiReviewing.value = true
  try {
    const result: any = await agentApi.multiAgentReview(contractId.value, agents)
    aiResult.value = {
      review_task_id: result.review_task_id,
      risk_level: result.merged_result?.risk_level,
      risk_score: result.merged_result?.risk_score,
      summary: result.merged_result?.summary,
      findings_count: result.merged_result?.total_findings,
    }
    showAiResult.value = true
    ElMessage.success('多Agent审查完成')
    fetchContract()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '多Agent审查失败')
  } finally {
    aiReviewing.value = false
  }
}

const handleGetModifications = async () => {
  modificationLoading.value = true
  try {
    const result: any = await contractsApi.getModificationSuggestions(contractId.value)
    modificationSuggestions.value = result.suggestions || []
    showModificationDialog.value = true
    selectedSuggestions.value = []
    if (modificationSuggestions.value.length === 0) {
      ElMessage.info('暂无修改建议，请先完成AI审查')
    }
  } catch (err: any) {
    console.error('获取修改建议失败:', err)
    ElMessage.error(err?.response?.data?.detail || err?.message || '获取修改建议失败，请稍后重试')
  } finally {
    modificationLoading.value = false
  }
}

const handleApplyModifications = async () => {
  if (selectedSuggestions.value.length === 0) {
    ElMessage.warning('请选择要应用的修改建议')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要应用选中的 ${selectedSuggestions.value.length} 个修改建议吗？`,
      '确认修改',
      { confirmButtonText: '应用', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  
  applyingModifications.value = true
  try {
    const result: any = await contractsApi.applyModifications(contractId.value, selectedSuggestions.value)
    ElMessage.success(result.message)
    showModificationDialog.value = false
    
    // 显示修改后内容
    modifiedContent.value = result.modified_content || ''
    diffSummary.value = result.diff_summary || ''
    showModifiedContent.value = true
    
    fetchContract()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '应用修改建议失败')
  } finally {
    applyingModifications.value = false
  }
}

const handleExportModified = async (cmd: string) => {
  // cmd 格式: "word-modified" | "pdf-clean" | "markdown-modified" 等
  const [format, version] = cmd.split('-')
  try {
    const response: any = await contractsApi.exportModifiedContract(contractId.value, format, version)
    
    // 从 Content-Disposition header 解析文件名
    const cd = response.headers?.['content-disposition'] || ''
    let filename = ''
    // 优先 filename*=UTF-8''xxx
    const starMatch = cd.match(/filename\*=UTF-8''(.+?)(?:;|$)/)
    if (starMatch) {
      filename = decodeURIComponent(starMatch[1])
    } else {
      const plainMatch = cd.match(/filename="?(.+?)"?(?:;|$)/)
      if (plainMatch) filename = plainMatch[1]
    }
    // fallback
    if (!filename) {
      const ext = format === 'word' ? 'docx' : format === 'pdf' ? 'pdf' : 'md'
      const vLabel = { modified: '修改版', clean: '清洁版', original: '原文版' }[version] || version
      filename = `${contract.value?.title || '合同'}_${vLabel}.${ext}`
    }
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('导出成功')
  } catch (err: any) {
    console.error('导出失败:', err)
    ElMessage.error('导出失败')
  }
}

const handleCompare = async () => {
  compareLoading.value = true
  showCompareDialog.value = true
  compareData.value = null
  
  try {
    const result: any = await contractsApi.compareWithOriginal(contractId.value)
    compareData.value = result
  } catch (err: any) {
    console.error('获取对比数据失败:', err)
    ElMessage.error('获取对比数据失败')
  } finally {
    compareLoading.value = false
  }
}

const exportCompare = async (format: 'word' | 'markdown') => {
  if (!compareData.value?.has_modifications) return
  
  try {
    const blob = await contractsApi.exportModifiedContract(contractId.value, format)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `合同对比_${contract.value?.title || 'export'}.${format === 'word' ? 'docx' : 'md'}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (err) {
    console.error('导出失败:', err)
    ElMessage.error('导出失败')
  }
}

const getPriorityType = (priority: string) => {
  const map: Record<string, string> = {
    critical: 'danger',
    high: 'warning',
    medium: 'info',
    low: 'success'
  }
  return (map[priority] || 'info') as any
}

const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = {
    critical: '必须修改',
    high: '强烈建议',
    medium: '建议修改',
    low: '可选修改'
  }
  return map[priority] || priority
}

const formatAmount = (amount: number) => {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(amount)
}

const getRiskColor = (level: string) => {
  const map: Record<string, string> = { high: 'danger', medium: 'warning', low: 'success' }
  return (map[level] || 'info') as any
}

const getRiskLabel = (level: string) => {
  const map: Record<string, string> = { high: '高风险', medium: '中风险', low: '低风险' }
  return map[level] || level
}

const getReviewStatusColor = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'danger',
  }
  return (map[status] || 'info') as any
}

const reviewStatusLabels: Record<string, string> = {
  pending: '待处理',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

const formatDate = (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm')

const renderMarkdown = (text: string) => {
  if (!text) return ''
  // Simple markdown rendering
  return text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\[已修改\]/g, '<span style="color: #67c23a; font-weight: bold;">[已修改]</span>')
    .replace(/\n/g, '<br>')
}

// ========== 审批工作流 ==========
const loadWorkflowDefinitions = async () => {
  try {
    workflowDefinitions.value = (await workflowsApi.getDefinitions() as any) || []
  } catch {
    workflowDefinitions.value = []
  }
}

const handleLaunchApproval = async () => {
  if (!selectedWorkflowId.value) {
    ElMessage.warning('请选择审批流程')
    return
  }
  launchingApproval.value = true
  try {
    const res = await workflowsApi.createInstance({
      workflowId: selectedWorkflowId.value,
      contractId: Number(route.params.id),
    })
    ElMessage.success('审批流程已发起')
    showApprovalDialog.value = false
    selectedWorkflowId.value = null
    router.push(`/workflows/${res.id}`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '发起失败')
  } finally {
    launchingApproval.value = false
  }
}

onMounted(() => {
  fetchContract()
  loadWorkflowDefinitions()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.info-section {
  margin-bottom: 24px;
}

/* 美化描述表格 */
.info-section :deep(.el-descriptions__label) {
  width: 100px;
  min-width: 100px;
  font-weight: 600;
  color: #606266;
  background-color: #fafafa !important;
  white-space: nowrap;
}

.info-section :deep(.el-descriptions__content) {
  color: #303133;
  padding: 12px 16px;
}

.info-section :deep(.el-descriptions__cell) {
  padding: 12px 16px;
}

.info-section :deep(.el-descriptions__body) {
  background-color: #fff;
}

/* 风险评估部分 */
.risk-section {
  margin-top: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 12px;
  border: 1px solid #ebeef5;
}

.risk-section h3 {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.risk-card {
  text-align: center;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.risk-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 12px;
}

.risk-score {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}

.score-value {
  font-size: 32px;
  font-weight: 700;
}

.score-unit {
  font-size: 16px;
  color: #909399;
}

.risk-time {
  font-size: 16px;
  color: #606266;
  font-weight: 500;
}

.review-section,
.version-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

.review-section h3,
.version-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.review-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.reviewer {
  color: #909399;
  font-size: 14px;
}

.review-summary {
  margin: 0;
  color: #606266;
  line-height: 1.6;
}

.risk-quantification-section {
  margin-top: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 12px;
  border: 1px solid #bae6fd;
}

.risk-quantification-section h3 {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.risk-summary {
  background: white;
  border-radius: 8px;
  padding: 16px;
}

.summary-card {
  text-align: center;
  padding: 16px;
  border-radius: 8px;
  background: #f8f9fa;
}

.summary-card.high { border-left: 4px solid #F56C6C; }
.summary-card.medium { border-left: 4px solid #E6A23C; }
.summary-card.low { border-left: 4px solid #67C23A; }
.summary-card.loss { border-left: 4px solid #909399; }

.summary-number {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.risk-quantification-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

.risk-quantification-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
}

.risk-summary {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.summary-card {
  text-align: center;
  padding: 12px;
  border-radius: 8px;
  background: white;
}

.summary-card.high { border-left: 4px solid #F56C6C; }
.summary-card.medium { border-left: 4px solid #E6A23C; }
.summary-card.low { border-left: 4px solid #67C23A; }
.summary-card.loss { border-left: 4px solid #909399; }

.summary-number {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.summary-label {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.summary-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.advanced-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

.advanced-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
}

.tab-content {
  padding: 8px 0;
}
</style>
