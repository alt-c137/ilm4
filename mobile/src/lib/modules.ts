/** Разделы: иконка и экран приложения для каждого ключа ModuleConfig. */
import { router } from 'expo-router';
import { Alert } from 'react-native';

import type { IconName } from '@/ui/kit';

import { t } from './i18n';
import { openWeb } from './links';

export const MODULE_ICON: Record<string, IconName> = {
  prayer: 'moon', buy: 'bag-handle', jobs: 'briefcase', services: 'construct', transport: 'car', map: 'location',
  health: 'medkit', migration: 'airplane', library: 'library', forum: 'chatbox-ellipses', news: 'newspaper',
  nikah: 'heart', chat: 'chatbubbles', wallet: 'wallet', refugee: 'home', learn: 'school', finance: 'cash',
  tracker: 'checkmark-circle', feed: 'albums', communities: 'people', assistant: 'sparkles', stories: 'aperture', shorts: 'film', gifts: 'gift', digital: 'laptop', realestate: 'business', invest: 'trending-up', sport: 'football', lawyers: 'scale', fun: 'happy',
};

// раздел → вид публикаций в API (/pubs/<вид>/)
export const PUB_OF: Record<string, string> = {
  buy: 'buy', jobs: 'jobs', services: 'services', transport: 'trips', health: 'doctors',
  migration: 'stories', library: 'books', forum: 'topics',
};

// раздел сайта → где «Добавить» (форма на сайте, открывается уже со входом)
export const ADD_PATH: Record<string, string> = {
  buy: '/buy/add/', jobs: '/jobs/add/', services: '/services/add/', transport: '/transport/add/', trips: '/transport/trips/add/', places: '/map/add/',
  doctors: '/health/add/', stories: '/migration/add/', books: '/library/add/', topics: '/forum/ask/',
};

export function openModule(key: string, status: string, name: string) {
  if (status !== 'on') {
    Alert.alert(name, t('Раздел скоро откроется, ин шаа Аллах.'));
    return;
  }
  if (key === 'prayer') return router.push('/prayer');
  if (key === 'chat') return router.push('/chats');
  if (key === 'nikah') return router.push('/nikah');
  if (key === 'news') return router.push('/news');
  if (key === 'map') return router.push('/places');
  if (key === 'wallet') return router.push('/wallet');
  if (key === 'tracker') return router.push('/tracker');
  if (key === 'feed') return router.push('/tab-feed');
  if (key === 'assistant') return router.push('/assistant');
  if (key === 'communities') return router.push('/space');
  if (PUB_OF[key]) return router.push(`/pubs/${PUB_OF[key]}`);
  return openWeb(`/${key}/`, true);
}

export const PUB_TITLES: Record<string, string> = {
  buy: 'Купля-продажа', jobs: 'Работа', services: 'Услуги и фриланс', transport: 'Перевозки', trips: 'Попутчики', places: 'Халяль-места',
  doctors: 'Врачи', stories: 'Истории переезда', books: 'Библиотека', topics: 'Форум',
};
