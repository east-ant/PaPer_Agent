import { readFile, readdir } from 'node:fs/promises'
import { extname, relative, resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname, '..')
const SRC = resolve(ROOT, 'src')

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) {
      files.push(...await collectFiles(path))
    } else if (['.js', '.jsx'].includes(extname(entry.name))) {
      files.push(path)
    }
  }
  return files
}

const errors = []
const files = await collectFiles(SRC)

for (const file of files) {
  const name = relative(ROOT, file).replaceAll('\\', '/')
  const content = await readFile(file, 'utf8')

  // pages, components, store에서 mock 파일 직접 import 금지
  if (!name.startsWith('src/api/') && /from\s+['"][^'"]*\/api\/mock\//.test(content)) {
    errors.push(`${name}: mock 파일을 직접 import하지 마세요. src/api/agent.js 또는 src/api/papers.js를 통해 사용하세요.`)
  }

  // 중복 export 감지
  const exportedNames = [...content.matchAll(/export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g)].map((m) => m[1])
  const duplicates = exportedNames.filter((n, i) => exportedNames.indexOf(n) !== i)
  if (duplicates.length > 0) {
    errors.push(`${name}: 중복 export 감지: ${[...new Set(duplicates)].join(', ')}`)
  }
}

if (errors.length > 0) {
  console.error('Frontend boundary check failed:')
  for (const error of errors) console.error(`- ${error}`)
  process.exitCode = 1
} else {
  console.log('Frontend boundary check passed.')
}
