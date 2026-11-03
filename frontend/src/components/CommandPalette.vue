<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Search } from "@element-plus/icons-vue";
import { listPapers } from "../api/papers";
import type { PaperSummary } from "../api";

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
  navigate: [name: string];
  search: [query: string];
  import: [];
  openPaper: [paperId: string];
}>();

type CommandGroup = "导航" | "操作";

type StaticCommand = {
  id: string;
  label: string;
  hint: string;
  keywords: string;
  group: CommandGroup;
  action: () => void;
};

const NAV_COMMANDS: StaticCommand[] = [
  {
    id: "nav-today",
    label: "今天",
    hint: "继续阅读 / 本周",
    keywords: "today 今日 阅读 首页",
    group: "导航",
    action: () => emit("navigate", "today"),
  },
  {
    id: "nav-library",
    label: "文献库",
    hint: "全部论文",
    keywords: "library 文献 论文 列表",
    group: "导航",
    action: () => emit("navigate", "library"),
  },
  {
    id: "nav-synthesis",
    label: "综合",
    hint: "问答 / 对比 / 矩阵",
    keywords: "synthesis 综合 对比 矩阵",
    group: "导航",
    action: () => emit("navigate", "synthesis"),
  },
  {
    id: "nav-feed",
    label: "跟进",
    hint: "订阅与 Feed",
    keywords: "feed 跟进 订阅",
    group: "导航",
    action: () => emit("navigate", "feed"),
  },
  {
    id: "nav-settings",
    label: "设置",
    hint: "模型 / 提醒 / 数据",
    keywords: "settings 设置 配置",
    group: "导航",
    action: () => emit("navigate", "settings"),
  },
];

const ACTION_COMMANDS: StaticCommand[] = [
  {
    id: "act-import",
    label: "导入论文",
    hint: "上传 PDF / 按标识导入",
    keywords: "import 导入 上传 pdf arxiv doi",
    group: "操作",
    action: () => emit("import"),
  },
];

const query = ref("");
const papers = ref<PaperSummary[]>([]);
const activeIndex = ref(0);
const inputRef = ref<HTMLInputElement | null>(null);
let searchTimer: number | null = null;

const staticCommands = computed(() => {
  const q = query.value.trim().toLowerCase();
  const all = [...NAV_COMMANDS, ...ACTION_COMMANDS];
  if (!q) {
    return all;
  }
  return all.filter((item) =>
    (item.label + " " + item.keywords).toLowerCase().includes(q),
  );
});

type Option = {
  id: string;
  label: string;
  hint: string;
  group: CommandGroup | "论文";
  run: () => void;
};

const options = computed<Option[]>(() => [
  ...staticCommands.value.map((item) => ({
    id: item.id,
    label: item.label,
    hint: item.hint,
    group: item.group,
    run: item.action,
  })),
  ...papers.value.map((paper) => ({
    id: paper.id,
    label: paper.title,
    hint: [(paper.authors ?? [])[0], paper.year].filter(Boolean).join(" · "),
    group: "论文" as const,
    run: () => emit("openPaper", paper.id),
  })),
]);

watch(
  () => props.visible,
  async (visible) => {
    if (!visible) {
      return;
    }
    query.value = "";
    papers.value = [];
    activeIndex.value = 0;
    await nextTick();
    inputRef.value?.focus();
  },
);

watch(query, (value) => {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
  const keyword = value.trim();
  if (keyword.length < 2) {
    papers.value = [];
    return;
  }
  searchTimer = window.setTimeout(async () => {
    try {
      papers.value = await listPapers({ query: keyword, limit: 8 });
    } catch {
      papers.value = [];
    }
  }, 180);
});

watch(
  () => options.value.length,
  () => {
    activeIndex.value = 0;
  },
);

function run(option: Option | undefined): void {
  if (!option) {
    return;
  }
  option.run();
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    emit("close");
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    activeIndex.value = Math.min(options.value.length - 1, activeIndex.value + 1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    activeIndex.value = Math.max(0, activeIndex.value - 1);
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    run(options.value[activeIndex.value]);
  }
}
</script>

<template>
  <div v-if="visible" class="palette" role="dialog" aria-modal="true" aria-label="命令面板">
    <div class="palette__backdrop" @click="emit('close')" />
    <section class="palette__panel" @click.stop>
      <label class="palette__search">
        <Search class="palette__icon" />
        <input
          ref="inputRef"
          v-model="query"
          type="text"
          placeholder="搜索论文、跳转或执行命令…"
          aria-label="命令搜索"
          @keydown="handleKeydown"
        />
        <kbd>ESC</kbd>
      </label>

      <div class="palette__list">
        <p v-if="!options.length" class="palette__empty">
          没有匹配项。输入至少 2 个字符可搜索论文。
        </p>
        <template v-for="(option, index) in options" :key="option.id">
          <p
            v-if="index === 0 || options[index - 1].group !== option.group"
            class="palette__group"
          >
            {{ option.group }}
          </p>
          <button
            type="button"
            class="palette__item"
            :class="{ 'is-active': index === activeIndex }"
            @mouseenter="activeIndex = index"
            @click="run(option)"
          >
            <span class="palette__label">{{ option.label }}</span>
            <span class="palette__hint">{{ option.hint }}</span>
          </button>
        </template>
      </div>

      <footer class="palette__footer">
        <span>↑↓ 选择</span>
        <span>Enter 执行</span>
        <span>Esc 关闭</span>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.palette {
  position: fixed;
  inset: 0;
  z-index: 60;
}

.palette__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(25, 23, 19, 0.3);
}

.palette__panel {
  position: relative;
  width: min(560px, calc(100vw - 48px));
  max-height: 62vh;
  margin: 12vh auto 0;
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: 0 24px 60px rgba(40, 33, 22, 0.22);
}

.palette__search {
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--color-border);
  padding: 12px 14px;
}

.palette__icon {
  width: 15px;
  color: var(--color-text-muted);
}

.palette__search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: 14px;
}

.palette__search kbd {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  padding: 1px 5px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.palette__list {
  max-height: calc(62vh - 96px);
  overflow-y: auto;
  padding: 6px 0;
}

.palette__group {
  margin: 8px 14px 4px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.palette__item {
  display: flex;
  width: 100%;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  padding: 9px 14px;
  text-align: left;
}

.palette__item.is-active {
  border-left-color: var(--color-accent);
  background: var(--color-surface-alt);
}

.palette__label {
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.palette__hint {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-size: 10px;
}

.palette__empty {
  margin: 0;
  padding: 22px 14px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.palette__footer {
  display: flex;
  gap: 16px;
  border-top: 1px solid var(--color-border);
  padding: 8px 14px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}
</style>
