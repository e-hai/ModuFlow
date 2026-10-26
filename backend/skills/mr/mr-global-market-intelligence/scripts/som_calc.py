#!/usr/bin/env python3
import sys, json
vol = int(sys.argv[1]) if len(sys.argv) > 1 else 120000
rate = float(sys.argv[2]) if len(sys.argv) > 2 else 0.035
arpu = float(sys.argv[3]) if len(sys.argv) > 3 else 1.85
print(json.dumps({'annual_installs': int(vol*12*rate), 'som_usd': round(vol*12*rate*arpu, 2)}))
