/**
 * LOCAL PROXY SERVER for Indiana CD-9 Democratic Targeting Guide
 * ---------------------------------------------------------------
 * Routes Anthropic API calls from the browser through this server,
 * avoiding CORS restrictions on direct browser-to-API requests.
 *
 * SETUP (one-time):
 *   npm install  OR  npm init -y   (no packages needed — uses Node built-ins only)
 *
 * USAGE:
 *   1. Edit API_KEY below with your Anthropic API key
 *   2. Run:  node proxy.js
 *   3. Open the .html file in your browser
 *   4. The page will automatically use http://localhost:3000
 */

const http  = require('http');
const https = require('https');

// ── Set your Anthropic API key here ──────────────────────────────────────────
const API_KEY = 'sk-ant-YOUR-KEY-HERE';
// ─────────────────────────────────────────────────────────────────────────────

const PORT = 3000;

const server = http.createServer((req, res) => {
  // CORS headers — allow requests from any origin (the local HTML file)
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Method not allowed' }));
    return;
  }

  // Collect request body
  let body = '';
  req.on('data', chunk => { body += chunk.toString(); });
  req.on('end', () => {
    const options = {
      hostname: 'api.anthropic.com',
      path:     '/v1/messages',
      method:   'POST',
      headers:  {
        'Content-Type':      'application/json',
        'Content-Length':    Buffer.byteLength(body),
        'x-api-key':         API_KEY,
        'anthropic-version': '2023-06-01',
      }
    };

    const apiReq = https.request(options, apiRes => {
      res.writeHead(apiRes.statusCode, { 'Content-Type': 'application/json' });
      apiRes.pipe(res);
    });

    apiReq.on('error', err => {
      console.error('API request error:', err.message);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Proxy error: ' + err.message }));
    });

    apiReq.write(body);
    apiReq.end();
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('');
  console.log('  Indiana CD-9 Targeting Guide — Local Proxy');
  console.log('  ──────────────────────────────────────────');
  console.log(`  Proxy running at: http://localhost:${PORT}`);
  console.log('  Open the .html file in your browser.');
  console.log('  Press Ctrl+C to stop.');
  console.log('');
});
