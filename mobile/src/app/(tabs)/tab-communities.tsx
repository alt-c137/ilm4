import { TabMode } from '@/ui/kit';

import Spaces from '../space/index';

/** «Сообщества» как нижняя вкладка — тот же экран, что открывается из «Сервисов». */
export default function CommunitiesTab() {
  return <TabMode.Provider value><Spaces /></TabMode.Provider>;
}
