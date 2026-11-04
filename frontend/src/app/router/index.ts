import { createRouter, createWebHashHistory } from "vue-router";
import { useAuth } from "@/shared/composables/useAuth";

const WorkbenchShell = () => import("@/app/layouts/WorkbenchShell.vue");
const AppShell = () => import("@/app/layouts/AppShell.vue");

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: { name: "today" } },
    {
      path: "/today",
      name: "today",
      component: WorkbenchShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/library",
      name: "library",
      component: WorkbenchShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/synthesis",
      name: "synthesis",
      component: WorkbenchShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/feed",
      name: "feed",
      component: WorkbenchShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/papers/:paperId",
      name: "paper",
      component: WorkbenchShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: WorkbenchShell,
      meta: { requiresAuth: true },
    },
    /* 旧对话与旧阅读器保留，避免书签失效；新入口是论文 Inspector。 */
    {
      path: "/chat",
      name: "chat",
      component: AppShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/sessions/:sessionId/reader",
      name: "session-reader",
      component: AppShell,
      meta: { requiresAuth: true },
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: { requiresAuth: false },
    },
    { path: "/:pathMatch(.*)*", redirect: { name: "today" } },
  ],
});

/** 鉴权守卫：首次导航等待 checkAuth 完成，避免刷新后误跳登录页。 */
router.beforeEach(async (to) => {
  const { ensureAuthLoaded, isAuthenticated } = useAuth();
  await ensureAuthLoaded();

  const requiresAuth = to.meta.requiresAuth === true;
  if (requiresAuth && !isAuthenticated.value) {
    return { name: "login" };
  }
  if (!requiresAuth && isAuthenticated.value) {
    return { name: "today" };
  }
  return true;
});

export default router;
