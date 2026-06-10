import json, sys, os

if len(sys.argv) >= 3:
    cmd = sys.argv[1]
    path = sys.argv[2]
    
    if cmd == 'read':
        try:
            with open(path, 'r', encoding='utf-8') as f:
                print(f.read())
        except:
            print('{}')
    
    elif cmd == 'write' and len(sys.argv) >= 4:
        data = sys.argv[3]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
