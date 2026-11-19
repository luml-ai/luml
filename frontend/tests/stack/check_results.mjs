// Fails a run in which any test was skipped, did not run or passed only on a retry, from the
// JSON report of Playwright: a green CI run then means every test ran and passed. A test marked
// test.fail() is a self-test of the error guard's fixture: it must fail by the guard's message.
//
//   node check_results.mjs <results.json>
import { readFileSync } from 'node:fs'

const report = JSON.parse(readFileSync(process.argv[2], 'utf-8'))
const problems = []
const GUARD_FAILURE = /unexpected error\(s\) in the browser|declared error\(s\) never seen/

function visit(suite, titles) {
  const path = suite.title ? [...titles, suite.title] : titles
  for (const child of suite.suites ?? []) visit(child, path)
  for (const spec of suite.specs ?? []) {
    for (const test of spec.tests) {
      // expected, unexpected, flaky or skipped; a test that never started is skipped too.
      const title = [...path, spec.title].join(' > ')
      if (test.status !== 'expected' && test.status !== 'unexpected')
        problems.push(`${test.status}: ${title}`)
      if (!test.annotations.some((annotation) => annotation.type === 'fail')) continue
      for (const result of test.results) {
        const messages = (result.errors ?? []).map((error) => error.message ?? '').join('\n')
        if (!GUARD_FAILURE.test(messages)) problems.push(`failed, not by the error guard: ${title}`)
      }
    }
  }
}

for (const suite of report.suites) visit(suite, [])
const { expected = 0, unexpected = 0 } = report.stats ?? {}
if (expected + unexpected === 0) problems.push('no test ran')
if (problems.length) {
  console.error(`${problems.length} test(s) did not run and pass cleanly:`)
  for (const problem of problems) console.error(`  ${problem}`)
  process.exit(1)
}
console.error(`[e2e] all ${expected} tests ran; none skipped or flaky`)
