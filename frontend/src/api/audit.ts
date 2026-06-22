import request from '@/utils/request'

export const auditApi = {
  listAuditLogs(params: {
    page?: number
    size?: number
    username?: string
    action?: string
    resource_type?: string
    status?: string
    start_date?: string
    end_date?: string
  }) {
    return request.get('/audit/audit-logs', { params })
  },

  countAuditLogs(params: Record<string, any>) {
    return request.get('/audit/audit-logs/count', { params })
  },

  listOperationLogs(params: {
    page?: number
    size?: number
    username?: string
    module?: string
    method?: string
    start_date?: string
    end_date?: string
  }) {
    return request.get('/audit/operation-logs', { params })
  },

  stats(days?: number) {
    return request.get('/audit/stats', { params: { days } })
  },
}
