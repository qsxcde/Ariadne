const isMac = /Mac|iPhone|iPad/i.test(window.navigator.platform);

/** 统一修饰键文案：Windows/Linux 显示 Ctrl，macOS 显示 ⌘。 */
export function shortcutLabel(key: string): string {
  return isMac ? `⌘${key}` : `Ctrl+${key}`;
}

export function modifierName(): string {
  return isMac ? "⌘" : "Ctrl";
}
