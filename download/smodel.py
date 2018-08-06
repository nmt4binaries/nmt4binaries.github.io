import pandas as pd
import numpy as np
import keras.backend as K
from keras.models import Model
from keras.models import load_model
from keras.layers import Input, Embedding, LSTM, Merge
from gensim import models
from gensim.models import KeyedVectors
from sklearn import metrics
from sklearn.metrics import roc_curve, auc, roc_auc_score
from keras.preprocessing.sequence import pad_sequences
import itertools
import matplotlib.pyplot as plt

TRAIN_CSV = 'train_set_O2.csv'
TEST_CSV = 'test_set_O2.csv'

saved_weights = "siamese_model_100DW2V_2HL_50HU_O2.hdf5"

# Load a trained w2v model
model = models.Word2Vec.load('100D_MinWordCount0_downSample1e-5_trained100epoch_L.w2v')
# Inpute size
w2v_dim = 100

n_units_2nd_layer = 50
n_units_1st_layer = 64

train_df = pd.read_csv(TRAIN_CSV)
test_df = pd.read_csv(TEST_CSV)

def text_to_word_list(text):
    
    text = str(text)
    text = text.upper()
    text = text.split()

    return text

vocabulary = dict()
 # '<unk>' will never be used, it is only a placeholder for the [0, 0, ....0] embedding
inverse_vocabulary = ['<unk>'] 
#word2vec = KeyedVectors.load_word2vec_format(EMBEDDING_FILE, binary=True)

questions_cols = ['x86_bb', 'arm_bb']
#
# Iterate over the questions only of both training and test datasets
for dataset in [train_df, test_df]:
    for index, row in dataset.iterrows():

        # Iterate through the text of both questions of the row
        for question in questions_cols:

            q2n = []  # q2n -> question numbers representation
            for word in text_to_word_list(row[question]):

                # Check for unwanted words
                if word not in model.wv:
                    print("Unknown workd is found!!!")
                    continue

                if word not in vocabulary:
                    vocabulary[word] = len(inverse_vocabulary)
                    q2n.append(len(inverse_vocabulary))
                    inverse_vocabulary.append(word)
                else:
                    q2n.append(vocabulary[word])

            # Replace questions as word to question as number representation
            dataset.set_value(index, question, q2n)
            
embedding_dim = w2v_dim
# This will be the embedding matrix
embeddings = 1 * np.random.randn(len(vocabulary) + 1, embedding_dim)  
embeddings[0] = 0  # So that the padding will be ignored

# Build the embedding matrix, please refer to the meeting slides for more detailed explanation
for word, index in vocabulary.items():
    if word in model.wv:
        embeddings[index] = model.wv[word]

max_seq_length=101

X2 = test_df[questions_cols]
Y2 = test_df['eq']

X_test = {'left': X2.x86_bb, 'right': X2.arm_bb}
Y_test = Y2.values

for dataset, side in itertools.product([X_test], ['left', 'right']):
    dataset[side] = pad_sequences(dataset[side], maxlen=max_seq_length)

def exponent_neg_manhattan_distance(left, right):
    ''' Helper function for the similarity estimate of the LSTMs outputs'''
    return K.exp(-K.sum(K.abs(left-right), axis=1, keepdims=True))


left_input = Input(shape=(max_seq_length,), dtype='int32')
right_input = Input(shape=(max_seq_length,), dtype='int32')

embedding_layer = Embedding(len(embeddings), embedding_dim, weights=[embeddings], \
                            input_length=max_seq_length, trainable=False)

# Embedded version of the inputs
encoded_left = embedding_layer(left_input)
encoded_right = embedding_layer(right_input)

# The 1st hidden layer
shared_lstm_01 = LSTM(n_units_1st_layer, return_sequences=True)
# The 2nd hidden layer
shared_lstm_02 = LSTM(n_units_2nd_layer, activation='relu')

left_output = shared_lstm_02(shared_lstm_01(encoded_left) )
right_output= shared_lstm_02(shared_lstm_01(encoded_right))

my_distance = Merge(mode=lambda x: exponent_neg_manhattan_distance(x[0], x[1]), \
                        output_shape=lambda x: (x[0][0], 1))([left_output, right_output])

# Pack it all up into a model
smodel = Model([left_input, right_input], [my_distance])
smodel.load_weights(saved_weights)

pred = smodel.predict([X_test['left'], X_test['right']])

fpr, tpr, _ = roc_curve(Y_test, pred, pos_label=1)
roc_auc = auc(fpr, tpr)*100

plt.figure()
plt.plot(fpr, tpr, color='red', linewidth = 1.2, label='Siamese Model (AUC = %0.2f%%)' % roc_auc)

plt.plot([0, 1], [0, 1], color = 'silver', linestyle = ':', linewidth = 1.2)
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate', fontsize=12)
plt.ylabel('True Positive Rate', fontsize=12)
plt.title('Receiver Operating Characteristic (ROC)')
plt.legend(loc="lower right")
plt.show()
