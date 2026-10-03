import { TabMode } from '@/ui/kit';

import PubList from '../pubs/[key]';

/** Этот раздел можно поставить нижней кнопкой (Профиль → «Нижние кнопки»). Экран тот же, что открывается из «Сервисов». */
export default function Tab() {
  return <TabMode.Provider value><PubList fixedKey="jobs" /></TabMode.Provider>;
}
