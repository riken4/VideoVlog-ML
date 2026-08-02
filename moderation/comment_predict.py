import os
import pickle

# Get the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File paths
MODEL_PATH = os.path.join(BASE_DIR, "comment_model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")

# Load the trained model
with open(MODEL_PATH, "rb") as model_file:
    model = pickle.load(model_file)

# Load the trained TF-IDF vectorizer
with open(VECTORIZER_PATH, "rb") as vectorizer_file:
    vectorizer = pickle.load(vectorizer_file)


def predict_comment(comment):
    """
    Predict whether a comment is Safe or Toxic.

    Parameters:
        comment (str): User comment.

    Returns:
        int:
            0 = Safe
            1 = Toxic
    """

    # Convert text into TF-IDF features
    comment_vector = vectorizer.transform([comment])

    # Predict using Logistic Regression
    prediction = model.predict(comment_vector)[0]

    return prediction