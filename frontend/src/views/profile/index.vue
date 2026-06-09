<template>
  <div class="profile">
    <el-card shadow="hover">
      <template #header><span>个人中心</span></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ userStore.userInfo?.username }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ userStore.userInfo?.name }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ userStore.userInfo?.email }}</el-descriptions-item>
        <el-descriptions-item label="部门">{{ userStore.userInfo?.department || '-' }}</el-descriptions-item>
        <el-descriptions-item label="职位">{{ userStore.userInfo?.position || '-' }}</el-descriptions-item>
        <el-descriptions-item label="最后登录">{{ userStore.userInfo?.last_login ? formatDate(userStore.userInfo.last_login) : '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import dayjs from 'dayjs'

const userStore = useUserStore()
const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')
</script>
