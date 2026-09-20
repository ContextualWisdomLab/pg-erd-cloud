import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import { extname, isAbsolute, relative, resolve } from 'node:path'

import { headersFor, securityHeaders } from './static-headers.mjs'

const root = resolve(process.env.STATIC_ROOT ?? '/app/dist')
const port = Number.parseInt(process.env.PORT ?? '8080', 10)

function isInsideRoot(filePath) {
  const rel = relative(root, filePath)
  return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel))
}

function requestPathToFile(url) {
  let pathname
  try {
    pathname = decodeURIComponent(new URL(url, 'http://localhost').pathname)
  } catch {
    return null
  }

  if (pathname.includes('\0')) return null

  const filePath = resolve(root, `.${pathname}`)
  return isInsideRoot(filePath) ? { filePath, pathname } : null
}

async function resolveStaticFile(requestedFile) {
  try {
    const fileStat = await stat(requestedFile)
    if (fileStat.isFile()) return requestedFile
    if (fileStat.isDirectory()) {
      const indexFile = resolve(requestedFile, 'index.html')
      const indexStat = await stat(indexFile)
      if (indexStat.isFile()) return indexFile
    }
  } catch {
    // Fall through to SPA fallback or 404 below.
  }

  if (extname(requestedFile)) return null

  const fallback = resolve(root, 'index.html')
  const fallbackStat = await stat(fallback)
  return fallbackStat.isFile() ? fallback : null
}

const server = createServer(async (req, res) => {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405, { Allow: 'GET, HEAD', ...securityHeaders })
    res.end()
    return
  }

  const requestTarget = requestPathToFile(req.url ?? '/')
  if (!requestTarget) {
    res.writeHead(400, securityHeaders)
    res.end('Bad request')
    return
  }

  const filePath = await resolveStaticFile(requestTarget.filePath)
  if (!filePath) {
    res.writeHead(404, securityHeaders)
    res.end('Not found')
    return
  }

  res.writeHead(200, headersFor(filePath, requestTarget.pathname))
  if (req.method === 'HEAD') {
    res.end()
    return
  }

  createReadStream(filePath)
    .on('error', () => {
      if (!res.headersSent) res.writeHead(500, securityHeaders)
      res.end('Internal server error')
    })
    .pipe(res)
})

server.listen(port, '0.0.0.0', () => {
  console.log(`static frontend server listening on ${port}`)
})

process.on('SIGTERM', () => {
  server.close(() => process.exit(0))
})
