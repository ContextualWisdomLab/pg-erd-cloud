const { performance } = require('perf_hooks');

function sanitizeHandleId_ArrayFrom(columnName) {
  const encoded = Array.from(columnName, (char) => {
    return char.codePointAt(0).toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

function sanitizeHandleId_ForOf(columnName) {
  if (!columnName) return 'c-empty';
  let encoded = '';
  let first = true;
  for (const char of columnName) {
    if (first) {
      first = false;
    } else {
      encoded += '-';
    }
    encoded += char.codePointAt(0).toString(16).padStart(4, '0');
  }
  return `c-${encoded}`;
}

const strings = [
  'id',
  'user_id',
  'created_at',
  'very_long_column_name_for_testing_performance',
  'id_가',
  'id_🚀'
];

function runBench(fn, name) {
  let res;
  const start = performance.now();
  for (let i = 0; i < 100000; i++) {
    for (const str of strings) {
      res = fn(str);
    }
  }
  console.log(`${name}: ${performance.now() - start}ms`);
  return res;
}

runBench(sanitizeHandleId_ArrayFrom, 'Array.from');
runBench(sanitizeHandleId_ForOf, 'for...of');
runBench(sanitizeHandleId_ArrayFrom, 'Array.from');
runBench(sanitizeHandleId_ForOf, 'for...of');
