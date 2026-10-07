from CHRLINE import CHRLINE
from base64 import b64encode
import json, os

token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiI5ZDlhYTljYS1hMmVlLTRlZDktYjRmOC0wMTM1MzJhMWY0MmMiLCJhdWQiOiJMSU5FIiwiaWF0IjoxNzkxMzYyNTAzLCJleHAiOjE3OTE5NjczMDMsInNjcCI6IkxJTkVfQ09SRSIsInJ0aWQiOiI4ZWYzZmM4Ny0wYmNkLTRjNmItYTg1NS01YThjYzU0Mjk1YjkiLCJyZXhwIjoxODIyODk4NTAzLCJ2ZXIiOiIzLjAiLCJhaWQiOiJ1MmQ1ZjM4NTU4NjM2YmI2ZWZkOGEzZTI2MWZiZWQ4YWIiLCJsc2lkIjoiNGU0ZDFmODYtMmMxZC00Y2RhLWEyYmEtMTJjZTBhODNiYjA5IiwiZGlkIjoiTk9ORSIsImN0eXBlIjoiREVTS1RPUF9XSU4iLCJjbW9kZSI6IlNFQ09OREFSWSIsImNpZCI6IjAxMDAwMDAwMDAifQ.OUr_dfAteyhP_AsYeRqgVeOxmnElV4nfGj2WAyNWBRY'
cl = CHRLINE(authTokenOrEmail=token, device='DESKTOPWIN', version='9.2.0.3421')

privK = b' \xe1\xe8\x13&+~YC\x19\xbe\x07\x04\xc6\xf0M\xaf\xfb=\x15\x05"\x13X\xb9\xffy\xa0\xf6\xaa3V'
pubK = b"P\xd6\xdb\xe8\x8bG>\x97\xd3\xa0,\xe1W\xb1\xb4U\xe3\x0bx\xb1R\xcfK\xe5\x15?e\xca\xce\x1f'T"
mid = 'u2d5f38558636bb6efd8a3e261fbed8ab'
keyId = 6058564
e2eeVersion = 1

cl.saveE2EESelfKeyData(mid, pubK, privK, keyId, e2eeVersion)
print('E2EE Key Saved Successfully!')
print('Verified key data:', cl.getE2EESelfKeyData(mid))
