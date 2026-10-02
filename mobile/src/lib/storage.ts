/** Хранилище: токен входа — в защищённом хранилище телефона (Keychain / Keystore),
 *  остальное (кеш, настройки) — в обычном AsyncStorage. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const TOKEN = 'ilm4.token';

export async function getToken(): Promise<string | null> {
  if (Platform.OS === 'web') return AsyncStorage.getItem(TOKEN);
  return SecureStore.getItemAsync(TOKEN);
}

export async function setToken(value: string | null) {
  if (Platform.OS === 'web') {
    if (value) await AsyncStorage.setItem(TOKEN, value);
    else await AsyncStorage.removeItem(TOKEN);
    return;
  }
  if (value) await SecureStore.setItemAsync(TOKEN, value);
  else await SecureStore.deleteItemAsync(TOKEN);
}

export async function load<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export async function save(key: string, value: unknown) {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* память переполнена — не критично, это кеш */
  }
}

/** Стереть кеш (выход из аккаунта): чужие данные не должны остаться на телефоне. */
export async function clearCache() {
  const keys = await AsyncStorage.getAllKeys();
  await AsyncStorage.multiRemove(keys.filter((k) => k.startsWith('cache:')));
}
