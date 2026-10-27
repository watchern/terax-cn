// 调试:验证原型链键是否被误替换
import fs from 'node:fs'
import path from 'node:path'

const dist = process.argv[2]
const file = path.join(dist, 'assets', 'main-Ab12Cd34.js')
const js = fs.readFileSync(file, 'utf8')
const i = js.indexOf('constructor')
console.log('constructor 上下文:', JSON.stringify(js.slice(Math.max(0, i - 40), i + 40)))
console.log('包含 const b="constructor":', js.includes('const b="constructor"'))
console.log('包含 const c="toString":', js.includes('const c="toString"'))
