import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '工作台', icon: 'DataBoard' },
      },
      {
        path: 'contracts',
        name: 'Contracts',
        redirect: '/contracts/list',
        meta: { title: '合同管理', icon: 'Document' },
        children: [
          {
            path: 'list',
            name: 'ContractList',
            component: () => import('@/views/contracts/list.vue'),
            meta: { title: '合同列表' },
          },
          {
            path: 'create',
            name: 'ContractCreate',
            component: () => import('@/views/contracts/create.vue'),
            meta: { title: '新建合同' },
          },
          {
            path: ':id',
            name: 'ContractDetail',
            component: () => import('@/views/contracts/detail.vue'),
            meta: { title: '合同详情', hidden: true },
          },
        ],
      },
      {
        path: 'reviews',
        name: 'Reviews',
        redirect: '/reviews/list',
        meta: { title: '合同审查', icon: 'Search' },
        children: [
          {
            path: 'list',
            name: 'ReviewList',
            component: () => import('@/views/reviews/list.vue'),
            meta: { title: '审查列表' },
          },
          {
            path: ':id',
            name: 'ReviewDetail',
            component: () => import('@/views/reviews/detail.vue'),
            meta: { title: '审查详情', hidden: true },
          },
        ],
      },
      {
        path: 'risks',
        name: 'Risks',
        redirect: '/risks/items',
        meta: { title: '风险管理', icon: 'Warning' },
        children: [
          {
            path: 'items',
            name: 'RiskItems',
            component: () => import('@/views/risks/items.vue'),
            meta: { title: '风险项' },
          },
          {
            path: 'rules',
            name: 'RiskRules',
            component: () => import('@/views/risks/rules.vue'),
            meta: { title: '风险规则' },
          },
        ],
      },
      {
        path: 'workflows',
        name: 'Workflows',
        redirect: '/workflows/instances',
        meta: { title: '工作流', icon: 'Connection' },
        children: [
          {
            path: 'instances',
            name: 'WorkflowInstances',
            component: () => import('@/views/workflows/instances.vue'),
            meta: { title: '流程实例' },
          },
          {
            path: 'definitions',
            name: 'WorkflowDefinitions',
            component: () => import('@/views/workflows/definitions.vue'),
            meta: { title: '流程定义' },
          },
        ],
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/users/index.vue'),
        meta: { title: '用户管理', icon: 'User', roles: ['superadmin', 'admin'] },
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('@/views/notifications/index.vue'),
        meta: { title: '消息通知', icon: 'Bell', hidden: true },
      },
      {
        path: 'agent',
        name: 'Agent',
        component: () => import('@/views/agent/index.vue'),
        meta: { title: 'AI智能体', icon: 'MagicStick' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '个人中心', hidden: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || ''} - 合同审查系统`
  
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
