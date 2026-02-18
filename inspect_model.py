from tensorflow import keras
import glob
for f in glob.glob('newapp/models/*lstm.keras'):
    print('===', f)
    m = keras.models.load_model(f)
    m.summary()
