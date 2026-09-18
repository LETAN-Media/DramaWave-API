import re

with open('app/services/canonical.py', 'r') as f:
    content = f.read()

new_content = content.replace(
    "for items in results_list:\n        for item in items:",
    "for items in results_list:\n        if isinstance(items, Exception):\n            continue\n        for item in items:"
)

with open('app/services/canonical.py', 'w') as f:
    f.write(new_content)
