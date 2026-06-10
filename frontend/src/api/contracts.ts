import request from '@/utils/request'
import type { ContractListParams, ContractCreateData } from '@/types/contract'

export const contractsApi = {
  list(params: ContractListParams) {
    return request.get('/contracts', { params })
  },

  get(id: number) {
    return request.get(`/contracts/${id}`)
  },

  create(data: ContractCreateData) {
    return request.post('/contracts', data)
  },

  update(id: number, data: Partial<ContractCreateData>) {
    return request.put(`/contracts/${id}`, data)
  },

  delete(id: number) {
    return request.delete(`/contracts/${id}`)
  },

  submit(id: number) {
    return request.post(`/contracts/${id}/submit`)
  },

  upload(file: File, title?: string) {
    const formData = new FormData()
    formData.append('file', file)
    if (title) formData.append('title', title)
    return request.post('/contracts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getVersions(id: number) {
    return request.get(`/contracts/${id}/versions`)
  },

  // 获取修改建议
  getModificationSuggestions(contractId: number, reviewTaskId?: number) {
    const params = reviewTaskId ? `?review_task_id=${reviewTaskId}` : ''
    return request.post(`/contracts/${contractId}/modification-suggestions${params}`)
  },

  // 应用修改建议
  applyModifications(contractId: number, suggestionIds: string[]) {
    return request.post(`/contracts/${contractId}/apply-modifications`, suggestionIds)
  },

  getFiles(id: number) {
    return request.get(`/contracts/${id}/files`)
  },

  aiReview(id: number) {
    return request.post(`/contracts/${id}/ai-review`)
  },
}
