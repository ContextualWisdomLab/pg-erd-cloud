const fs = require('fs');

const path = 'frontend/src/App.coverage.test.tsx';
let code = fs.readFileSync(path, 'utf8');

const originalCode = `  it('logs auto-layout failures and preserves nodes added after the undo snapshot', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    vi.useFakeTimers()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)`;

const newCode = `  it('logs auto-layout failures and preserves nodes added after the undo snapshot', async () => {
    await renderReadyApp()
    fireEvent.click(screen.getByRole('button', { name: '다이어그램' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: '열기' }).length).toBeGreaterThan(0))
    vi.useFakeTimers()
    fireEvent.click(screen.getAllByRole('button', { name: '열기' })[0]!)`;

if (code.includes(originalCode)) {
  code = code.replace(originalCode, newCode);
  fs.writeFileSync(path, code);
  console.log('Patched App.coverage.test.tsx');
} else {
  console.log('Original code not found in App.coverage.test.tsx');
}
