const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const root = __dirname;
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
const allowed = new Set(['/fbx_preview.html', '/fbx_preview.js', '/fbx_preview.css']);
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const name = pathname === '/' ? '/fbx_preview.html' : pathname;
  if (!allowed.has(name) && !name.startsWith('/node_modules/three/')) {
    res.writeHead(404).end('Not found');
    return;
  }
  const file = path.resolve(root, '.' + name);
  if (!file.startsWith(root + path.sep)) {
    res.writeHead(403).end('Forbidden');
    return;
  }
  fs.readFile(file, (error, data) => {
    if (error) {
      res.writeHead(404).end('Not found');
      return;
    }
    if (name === '/node_modules/three/examples/jsm/loaders/FBXLoader.js') {
      data = data.toString('utf8').replace(
        'const animationCurveID = relationships.parents[ 0 ].ID;',
        'const animationCurveID = relationships.parents[ 0 ].ID;\n\t\t\t\tif ( ! curveNodesMap.has( animationCurveID ) ) continue;'
      );
    }
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    res.end(data);
  });
});
server.listen(Number(process.env.PORT || 8765), '127.0.0.1', () => {
  console.log(`FBX preview: http://127.0.0.1:${server.address().port}`);
});
