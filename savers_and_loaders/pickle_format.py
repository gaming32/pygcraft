import pickle

def save(name, **parts):
    print('insave')
    file = open('saves/%s.pkl' % name, 'wb')
    pickle.dump(parts, file)
    file.close()

def load(name):
    file = open('saves/%s.pkl' % name, 'rb')
    val = pickle.load(file)
    file.close()
    return val