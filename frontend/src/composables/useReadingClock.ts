import { onBeforeUnmount, onMounted, watch, type Ref } from "vue";

import { recordReadingTime } from "../api/papers";

const TICK_MS = 5000;
const FLUSH_SECONDS = 60;

/**
 * 统计当前论文的可见阅读时长，按分钟批次上报。
 *
 * 只在前台累计；切到后台或离开论文时立即 flush，避免丢失最后一段时间。
 */
export function useReadingClock(paperId: Ref<string>) {
  let timer: number | null = null;
  let readingPaperId = "";
  let pendingSeconds = 0;

  function flush(): void {
    const seconds = Math.min(Math.floor(pendingSeconds), 3600);
    pendingSeconds = 0;
    if (seconds < 5 || !readingPaperId) {
      return;
    }
    void recordReadingTime(readingPaperId, seconds).catch(() => undefined);
  }

  function start(): void {
    readingPaperId = paperId.value;
    if (timer !== null) {
      return;
    }
    timer = window.setInterval(() => {
      if (window.document.visibilityState !== "visible") {
        return;
      }
      pendingSeconds += TICK_MS / 1000;
      if (pendingSeconds >= FLUSH_SECONDS) {
        flush();
      }
    }, TICK_MS);
  }

  function stop(): void {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
    flush();
  }

  function handleVisibilityChange(): void {
    if (window.document.visibilityState !== "visible") {
      flush();
    }
  }

  onMounted(() => {
    start();
    window.document.addEventListener("visibilitychange", handleVisibilityChange);
  });

  watch(paperId, () => {
    stop();
    start();
  });

  onBeforeUnmount(() => {
    stop();
    window.document.removeEventListener("visibilitychange", handleVisibilityChange);
  });

  return { start, stop, flush };
}
