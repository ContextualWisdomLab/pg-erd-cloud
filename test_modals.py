# This script will check the exact changes to the modals
with open("frontend/src/components/modals/EditTableModal.tsx") as f:
    content = f.read()
    if 'aria-label="닫기"' in content and '<span aria-hidden="true">✕</span>' in content:
        print("EditTableModal: OK")

with open("frontend/src/components/modals/ExportModal.tsx") as f:
    content = f.read()
    if 'aria-label="공유 및 내보내기 닫기"' in content and '<span aria-hidden="true">✕</span>' in content:
        print("ExportModal: OK")
