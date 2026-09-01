import pickle
import os

BASE_DIR = r'd:\videovlogml try2\social-media\moderation'
MODEL_PATH = os.path.join(BASE_DIR, 'xgb_comment_model (2).pkl')
VECTORIZER_PATH = os.path.join(BASE_DIR, 'vectorizer (1).pkl')

print('Loading model...')
with open(MODEL_PATH, 'rb') as f:
    model = pickle.load(f)
print(f'✓ Model loaded: {type(model)}')

print('Loading vectorizer...')
with open(VECTORIZER_PATH, 'rb') as f:
    vectorizer = pickle.load(f)
print(f'✓ Vectorizer loaded: {type(vectorizer)}')

print('\n--- Testing Predictions ---')
test_comments = [
    'you are an idiot',
    'This is a great video!',
    'I hate this',
    'Love your content',
    'You suck'
]

for comment in test_comments:
    text_vector = vectorizer.transform([comment])
    probability = model.predict_proba(text_vector)[0][1]
    prediction = 1 if probability >= 0.40 else 0
    status = 'TOXIC (BLOCKED)' if prediction == 1 else 'CLEAN (ALLOWED)'
    print(f'{comment:30} -> {probability:.4f} -> {status}')
