/** Загрузка данных с кешем: мгновенно показываем сохранённое, затем обновляем с сервера. */
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, cachedGet, peekCache } from '@/lib/api';
import { useApp } from '@/state/app';

export function useFetch<T = any>(path: string | null, deps: unknown[] = []) {
  const { langTick, user } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState<ApiError | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const alive = useRef(true);

  const reload = useCallback(async (silent = false) => {
    if (!path) return;
    if (!silent) setLoading(true);
    try {
      const r = await cachedGet<T>(path);
      if (!alive.current) return;
      setData(r.data);
      setFromCache(r.fromCache);
      setError(null);
    } catch (e) {
      if (alive.current) setError(e instanceof ApiError ? e : new ApiError(String(e)));
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    if (path) {
      peekCache<T>(path).then((old) => {
        if (alive.current && old !== null) setData((cur) => cur ?? old);
      });
      // eslint-disable-next-line react-hooks/set-state-in-effect -- загрузка данных при смене адреса/языка/аккаунта
      reload();
    }
    return () => {
      alive.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, langTick, user?.id, ...deps]);

  return { data, setData, loading, error, fromCache, reload };
}
