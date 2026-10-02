import { TabMode } from '@/ui/kit';

import News from '../news/index';

/** Этот раздел можно поставить нижней кнопкой (Профиль → «Нижние кнопки»). Экран тот же, что открывается из «Сервисов». */
export default function Tab() {
  return <TabMode.Provider value><News /></TabMode.Provider>;
}
