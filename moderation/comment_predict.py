import os
import pickle
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "xgb_comment_model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")


# Load model
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

# Load vectorizer
with open(VECTORIZER_PATH, "rb") as f:
    vectorizer = pickle.load(f)


def normalize_comment(text):

    # Convert to lowercase
    text = text.lower()

    # Remove leading/trailing whitespace
    text = text.strip()

    # Remove numbers attached directly to the end of a word
    # stupid123 -> stupid
    # idiot123 -> idiot
    text = re.sub(r'([a-z]+)\d+$', r'\1', text)

    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text)

    return text


def predict_comment(comment_text):

    normalized_text = normalize_comment(comment_text)

    print(f"Original Comment: {comment_text}")
    print(f"Normalized Comment: {normalized_text}")

    text_vector = vectorizer.transform([normalized_text])

    probability = model.predict_proba(text_vector)[0][1]

    print(f"Toxic Probability: {probability}")

    if probability >= 0.40:
        return 1

    return 0