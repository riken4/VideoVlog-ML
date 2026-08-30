
def predict_comment(comment_text):

    text_vector = vectorizer.transform([comment_text])

    probability = model.predict_proba(text_vector)[0][1]

    print(f"{comment_text} -> {probability}")

    return probability