#!/usr/bin/env python3
from pathlib import Path
import json
p = Path('index.html')
print(json.dumps({'exists': p.exists(), 'size': p.stat().st_size if p.exists() else 0}))
