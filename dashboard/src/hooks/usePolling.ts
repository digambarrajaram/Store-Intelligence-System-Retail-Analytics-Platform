import { useEffect, useRef, useState } from 'react';

export const usePolling = <T>(
  fetchFn: () => Promise<T>,
  interval: number,
  options: { immediate?: boolean } = {}
) => {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(options.immediate ?? true);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const fetchData = async () => {
      if (!mountedRef.current) return;
      setIsLoading(true);
      setError(null);
      try {
        const result = await fetchFn();
        if (mountedRef.current) {
          setData(result);
          setIsLoading(false);
        }
      } catch (e) {
        if (mountedRef.current) {
          setError(e instanceof Error ? e.message : 'Unknown error');
          setIsLoading(false);
        }
      }
    };

    if (options.immediate ?? true) {
      fetchData();
    }

    const timer = setInterval(fetchData, interval);

    return () => {
      mountedRef.current = false;
      clearInterval(timer);
    };
  }, [fetchFn, interval, options.immediate]);

  return { data, error, isLoading };
};