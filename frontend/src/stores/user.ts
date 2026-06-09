import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import type { UserInfo } from '@/types/user'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const refreshToken = ref<string>(localStorage.getItem('refreshToken') || '')
  const userInfo = ref<UserInfo | null>(null)
  const roles = ref<string[]>([])

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    refreshToken.value = res.refresh_token
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('refreshToken', res.refresh_token)
    return res
  }

  async function getUserInfo() {
    const res = await authApi.getCurrentUser()
    userInfo.value = res
    roles.value = res.roles?.map((r: any) => r.code) || []
    return res
  }

  function logout() {
    token.value = ''
    refreshToken.value = ''
    userInfo.value = null
    roles.value = []
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
  }

  function hasRole(role: string) {
    return roles.value.includes(role) || roles.value.includes('superadmin')
  }

  function hasAnyRole(roleList: string[]) {
    return roleList.some(r => hasRole(r))
  }

  return {
    token,
    refreshToken,
    userInfo,
    roles,
    login,
    getUserInfo,
    logout,
    hasRole,
    hasAnyRole,
  }
})
