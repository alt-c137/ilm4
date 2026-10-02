/** Входящие звонки на любом экране приложения: личный канал /ws/me/ (как всплывашка на сайте). */
let openThread: number | null = null;

/** Какой диалог сейчас открыт — в нём звонок покажет сам экран чата, всплывашка не нужна. */
export function setOpenThread(id: number | null) {
  openThread = id;
}
export function getOpenThread() {
  return openThread;
}
