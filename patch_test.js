const fs = require('fs');

let testCode = fs.readFileSync('frontend/src/App.nativeFormSubmission.test.tsx', 'utf8');
testCode = testCode.replace(
  "await screen.findByRole('heading', { name: '대시보드' })\n\n    const projectName = screen.getByLabelText('New project')",
  "await screen.findByRole('heading', { name: '대시보드' })\n\n    await user.click(screen.getByRole('button', { name: '편집기' }))\n\n    const projectName = await screen.findByLabelText('New project')"
);

fs.writeFileSync('frontend/src/App.nativeFormSubmission.test.tsx', testCode, 'utf8');
