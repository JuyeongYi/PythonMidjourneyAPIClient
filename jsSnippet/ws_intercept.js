  const OrigWebSocket = window.WebSocket;
  window.WebSocket = function(...args) {
    console.log('[WS OPEN]', args[0]);
    const ws = new OrigWebSocket(...args);
    ws.addEventListener('message', function(event) {
      const d = typeof event.data === 'string' ? event.data : '[binary]';
      if (d.length < 5000) console.log('[WS RECV]', d.substring(0, 500));
    });
    const origSend = ws.send.bind(ws);
    ws.send = function(data) {
      console.log('[WS SEND]', data);
      return origSend(data);
    };
    return ws;
  };
  window.WebSocket.prototype = OrigWebSocket.prototype;