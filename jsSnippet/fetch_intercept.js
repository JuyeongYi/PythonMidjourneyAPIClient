  const _fetch = window.fetch;
  window.fetch = async (...args) => {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
    const method = args[1]?.method || 'GET';
    if (url?.includes('/api/')) {
      console.log(`[API] ${method} ${url}`);
      if (args[1]?.body) console.log('[BODY]', args[1].body);
      const res = await _fetch(...args);
      const clone = res.clone();
      clone.json().then(data => console.log('[RESP]', url, JSON.stringify(data, null, 2))).catch(() => {});
      return res;
    }
    return _fetch(...args);
  };