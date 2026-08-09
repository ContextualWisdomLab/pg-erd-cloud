const { vi } = require('vitest');

const fn = vi.fn(() => 'base');
fn.mockReturnValueOnce('once');
console.log(fn()); // once
fn.mockReturnValueOnce('once2');
fn.mockReset();
fn.mockImplementation(() => 'base2');
console.log(fn()); // base2
