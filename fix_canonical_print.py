with open('app/services/canonical.py', 'r') as f:
    content = f.read()

content = content.replace("out = []", "out = []\n    print('seen_series count:', len(seen_series))")
content = content.replace("return [c.model_dump()", "print('out count:', len(out))\n    return [c.model_dump()")

with open('app/services/canonical.py', 'w') as f:
    f.write(content)
