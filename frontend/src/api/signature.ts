import request from '@/utils/request'

export const signatureApi = {
  // 印章
  listSeals(activeOnly?: boolean) {
    return request.get('/signature/seals', { params: { active_only: activeOnly } })
  },
  createSeal(data: any) {
    return request.post('/signature/seals', data)
  },
  toggleSeal(id: number) {
    return request.put(`/signature/seals/${id}/toggle`)
  },
  deleteSeal(id: number) {
    return request.delete(`/signature/seals/${id}`)
  },

  // 签章请求
  listRequests(params: any) {
    return request.get('/signature/requests', { params })
  },
  countRequests(params: any) {
    return request.get('/signature/requests/count', { params })
  },
  createRequest(data: any) {
    return request.post('/signature/requests', data)
  },
  signRequest(id: number) {
    return request.post(`/signature/requests/${id}/sign`)
  },
  rejectRequest(id: number, reason?: string) {
    return request.post(`/signature/requests/${id}/reject`, null, { params: { reason } })
  },
  revokeRequest(id: number) {
    return request.post(`/signature/requests/${id}/revoke`)
  },
  verifySignature(id: number) {
    return request.get(`/signature/requests/${id}/verify`)
  },
  signatureLogs(id: number) {
    return request.get(`/signature/requests/${id}/logs`)
  },
}
