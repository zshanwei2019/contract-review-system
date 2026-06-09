<template>
  <div class="error-page">
    <div class="error-content">
      <h1>404</h1>
      <p>抱歉，您访问的页面不存在</p>
      <el-button type="primary" @click="router.push('/dashboard')">返回首页</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.error-page { height: 100vh; display: flex; align-items: center; justify-content: center; }
.error-content { text-align: center; }
.error-content h1 { font-size: 120px; color: #1890ff; margin: 0; }
.error-content p { font-size: 18px; color: #666; margin: 16px 0 32px; }
</style>
