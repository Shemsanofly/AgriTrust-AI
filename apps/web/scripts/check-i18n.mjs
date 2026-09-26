// Fails if Kiswahili and English differ in keys or {{placeholders}}, or if the code
// uses a static translation key that is missing.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const load = (lang) => JSON.parse(readFileSync(new URL(`../src/i18n/${lang}.json`, import.meta.url)))
const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([k, v]) => (typeof v === 'object' ? flatten(v, `${prefix}${k}.`) : [[`${prefix}${k}`, v]]))
const sw = new Map(flatten(load('sw')))
const en = new Map(flatten(load('en')))
const vars = (s) => [...s.matchAll(/{{\s*(\w+)\s*}}/g)].map((m) => m[1]).sort().join(',')
const problems = []

for (const [key, text] of en) {
  if (!sw.has(key)) problems.push(`missing in sw: ${key}`)
  else if (vars(text) !== vars(sw.get(key))) problems.push(`placeholder mismatch: ${key}`)
}
for (const key of sw.keys()) if (!en.has(key)) problems.push(`missing in en: ${key}`)

const walk = (dir) => readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? walk(join(dir, f)) : [join(dir, f)]))
const src = new URL('../src', import.meta.url).pathname
for (const file of walk(src).filter((f) => /\.tsx?$/.test(f))) {
  const code = readFileSync(file, 'utf8')
  for (const m of code.matchAll(/\bt\('([a-zA-Z0-9_.]+)'/g)) if (!en.has(m[1])) problems.push(`unknown key ${m[1]} in ${file}`)
  for (const m of code.matchAll(/key: '([a-z]+\.[a-zA-Z0-9_.]+)'/g)) if (!en.has(m[1])) problems.push(`unknown key ${m[1]} in ${file}`)
}

if (problems.length) {
  console.error(problems.join('\n'))
  process.exit(1)
}
console.log(`i18n OK: ${en.size} keys in sw + en`)
