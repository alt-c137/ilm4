import { TabMode } from '@/ui/kit';

import Places from '../places';

/** Этот раздел можно поставить нижней кнопкой (Профиль → «Нижние кнопки»). Экран тот же, что открывается из «Сервисов». */
export default function Tab() {
  return <TabMode.Provider value><Places /></TabMode.Provider>;
}
