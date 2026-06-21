import subprocess

title = "🧪 [testing improvement] Add missing test for jwt.decode error path"
body = """🎯 **What:** The testing gap addressed is the missing test for the error path when `jwt.decode` fails (e.g. invalid signature, expired token) in `auth.py`.
📊 **Coverage:** Now tests the scenario where `jwt.decode` raises an exception, ensuring it properly raises a 401 `HTTPException` with the detail message 'token verification failed'.
✨ **Result:** Improved test coverage for OIDC authentication by making sure that token verification failures are correctly handled and converted to a 401 response."""

# Use python to call the built-in submit tool
print("Will submit directly using tool call")
