import os
import pickle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "xgb_comment_model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")

# Load model
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

# Load vectorizer
with open(VECTORIZER_PATH, "rb") as f:
    vectorizer = pickle.load(f)


def predict_comment(comment_text):

    text_vector = vectorizer.transform([comment_text])

    probability = model.predict_proba(text_vector)[0][1]

    print(f"Comment: {comment_text}")
    print(f"Toxic Probability: {probability}")

    if probability >= 0.40:
        return 1

    return 0