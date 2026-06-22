<template>
  <el-container class="main-layout">
    <!-- 侧边栏 — 桌面端固定 -->
    <el-aside v-if="!isMobile" :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <img src="@/assets/logo.svg" alt="logo" class="logo-img" />
        <span v-show="!isCollapse" class="logo-text">合同审查系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :router="true"
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#1890ff"
        class="sidebar-menu"
      >
        <template v-for="route in menuRoutes" :key="route.path">
          <el-menu-item v-if="!route.children || route.children.length === 1" :index="getMenuPath(route)">
            <el-icon><component :is="route.meta?.icon" /></el-icon>
            <template #title>{{ route.meta?.title }}</template>
          </el-menu-item>
          <el-sub-menu v-else :index="route.path">
            <template #title>
              <el-icon><component :is="route.meta?.icon" /></el-icon>
              <span>{{ route.meta?.title }}</span>
            </template>
            <el-menu-item v-for="child in getVisibleChildren(route)" :key="child.path" :index="`/${route.path}/${child.path}`">
              {{ child.meta?.title }}
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <!-- 侧边栏 — 移动端抽屉 -->
    <el-drawer v-model="drawerVisible" direction="ltr" :size="260" :with-header="false" class="mobile-drawer">
      <div class="sidebar mobile-sidebar">
        <div class="logo">
          <img src="@/assets/logo.svg" alt="logo" class="logo-img" />
          <span class="logo-text">合同审查系统</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          :router="true"
          background-color="#001529"
          text-color="#ffffffa6"
          active-text-color="#1890ff"
          class="sidebar-menu"
          @select="drawerVisible = false"
        >
          <template v-for="route in menuRoutes" :key="route.path">
            <el-menu-item v-if="!route.children || route.children.length === 1" :index="getMenuPath(route)">
              <el-icon><component :is="route.meta?.icon" /></el-icon>
              <template #title>{{ route.meta?.title }}</template>
            </el-menu-item>
            <el-sub-menu v-else :index="route.path">
              <template #title>
                <el-icon><component :is="route.meta?.icon" /></el-icon>
                <span>{{ route.meta?.title }}</span>
              </template>
              <el-menu-item v-for="child in getVisibleChildren(route)" :key="child.path" :index="`/${route.path}/${child.path}`">
                {{ child.meta?.title }}
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </div>
    </el-drawer>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="header-left">
          <!-- 桌面端折叠按钮 -->
          <el-icon v-if="!isMobile" class="collapse-btn" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <!-- 移动端汉堡菜单 -->
          <el-icon v-else class="collapse-btn" @click="drawerVisible = true">
            <Menu />
          </el-icon>

          <el-breadcrumb separator="/" v-if="!isMobile">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
          <span v-else class="mobile-title">{{ currentTitle }}</span>
        </div>

        <div class="header-right">
          <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="notification-badge">
            <el-icon class="header-icon" @click="router.push('/notifications')">
              <Bell />
            </el-icon>
          </el-badge>
          <el-dropdown @command="handleCommand" trigger="click">
            <div class="user-info">
              <el-avatar :size="32" icon="UserFilled" />
              <span v-if="!isMobile" class="username">{{ userStore.userInfo?.name || '用户' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile"><el-icon><User /></el-icon>个人中心</el-dropdown-item>
                <el-dropdown-item command="password"><el-icon><Lock /></el-icon>修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容 -->
      <el-main class="content" :class="{ 'mobile-content': isMobile }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <keep-alive :include="cachedViews">
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { notificationsApi } from '@/api/notifications'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isCollapse = ref(false)
const unreadCount = ref(0)
const cachedViews = ref<string[]>([])
const drawerVisible = ref(false)

// 响应式检测
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

function onResize() { windowWidth.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

const menuRoutes = computed(() => {
  const mainRoute = router.options.routes.find(r => r.path === '/')
  return mainRoute?.children?.filter(r => !r.meta?.hidden) || []
})

const activeMenu = computed(() => route.path)

const currentTitle = computed(() => {
  const matched = route.matched.filter(r => r.meta?.title)
  return matched.length ? matched[matched.length - 1].meta?.title : ''
})

const breadcrumbs = computed(() => {
  const matched = route.matched.filter(r => r.meta?.title)
  return matched.map(r => ({ path: r.path, title: r.meta?.title as string }))
})

const getMenuPath = (route: any) => {
  if (route.children && route.children.length === 1) {
    return `/${route.path}/${route.children[0].path}`
  }
  return `/${route.path}`
}

const getVisibleChildren = (route: any) => {
  return route.children?.filter((c: any) => !c.meta?.hidden) || []
}

const getUnreadCount = async () => {
  try {
    const res: any = await notificationsApi.getCount()
    unreadCount.value = res.unread || 0
  } catch {}
}

const handleCommand = async (command: string) => {
  switch (command) {
    case 'profile': router.push('/profile'); break
    case 'password': break
    case 'logout':
      await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
      userStore.logout()
      router.push('/login')
      break
  }
}

onMounted(() => {
  userStore.getUserInfo()
  getUnreadCount()
})
</script>

<style scoped>
.main-layout { height: 100vh; }

.sidebar {
  background: #001529;
  transition: width 0.3s;
  overflow-y: auto;
  overflow-x: hidden;
}
.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 3px; }
.sidebar::-webkit-scrollbar-track { background: transparent; }

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  background: rgba(255,255,255,0.05);
}
.logo-img { width: 32px; height: 32px; }
.logo-text { color: #fff; font-size: 16px; font-weight: 600; margin-left: 12px; white-space: nowrap; }

.sidebar-menu { border-right: none; min-height: calc(100vh - 64px); }
.sidebar-menu:not(.el-menu--collapse) { width: 220px; }
.sidebar-menu .el-sub-menu__title, .sidebar-menu .el-menu-item { height: 50px; line-height: 50px; }
.sidebar-menu .el-menu--inline { background: #000c17 !important; }
.sidebar-menu .el-menu--inline .el-menu-item { padding-left: 56px !important; min-width: auto; }

.main-container { flex-direction: column; }

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
  z-index: 10;
}
.header-left { display: flex; align-items: center; gap: 16px; }
.collapse-btn { font-size: 20px; cursor: pointer; color: #333; }
.header-right { display: flex; align-items: center; gap: 20px; }
.header-icon { font-size: 20px; cursor: pointer; color: #333; }
.notification-badge { line-height: 1; }
.user-info { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.username { font-size: 14px; color: #333; }

.content { background: #f0f2f5; padding: 24px; overflow-y: auto; }

.mobile-title { font-size: 16px; font-weight: 600; color: #333; }
.mobile-content { padding: 12px; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ========== 移动端全局适配 ========== */
@media (max-width: 768px) {
  .header { padding: 0 12px; height: 56px; }
  .header-right { gap: 12px; }
  .mobile-content { padding: 8px !important; }
}
</style>

/* ========== 全局移动端样式（非 scoped） ========== */
<style>
/* 移动端表格卡片化 */
@media (max-width: 768px) {
  .el-table { font-size: 13px; }
  .el-table th .cell { white-space: nowrap; }
  .el-card { margin-bottom: 8px; }
  .el-card__body { padding: 12px; }
  .el-dialog { width: 92% !important; margin: 0 auto !important; }
  .el-form-item__label { font-size: 13px; }
  .el-input, .el-select, .el-date-editor { width: 100% !important; }
  .el-pagination { justify-content: center; }
  .el-statistic { font-size: 13px; }
  .el-tabs__content { padding: 8px !important; }
  .search-bar { flex-wrap: wrap; gap: 8px !important; }
  .search-bar .el-input, .search-bar .el-select { width: auto !important; flex: 1; min-width: 120px; }
}

/* 移动端抽屉侧边栏 */
.mobile-drawer .el-drawer__body { padding: 0; }
.mobile-sidebar { height: 100vh; }
</style>
