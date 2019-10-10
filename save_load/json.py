import json
import main

def save(name, **parts):
    parts['world'] = parts['world'].world
    __import__('pprint').pprint(parts)
    file = open('saves/%s.json' % name, 'w')
    json.dump(parts, file)
    file.close()

def load(name):
    file = open('saves/%s.json' % name, 'r')
    val = json.load(file)
    file.close()
    val['world'] = main.Model(val['world'])
    return val