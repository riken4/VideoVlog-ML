import os
import sys
import pickle
import pandas as pd
import django

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


def train():
    # Project root (folder containing manage.py)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, BASE_DIR)

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "social_media.settings"
    )

    django.setup()

    from post.models import Post

    posts = (Post.objects.select_related("author").order_by("id")
)
    data = []

    for post in posts:
        data.append({
            "id": post.id,
            "author": post.author.username,
            "title": post.title if post.title else "",
            "content": post.content if post.content else "",
            "likes": post.total_likes,
            "comments": post.total_comments,
        })

    df = pd.DataFrame(data)

    if df.empty:
        raise ValueError("No posts found in the database. Upload some posts first.")

    # Combine title, content, and author
    df["text"] = (
        df["title"].fillna("") + " " +
        df["content"].fillna("") + " " +
        df["author"].fillna("")
    )

    # Clean text
    df["text"] = df["text"].str.lower().str.strip()

    tfidf = TfidfVectorizer(
        stop_words="english",
        max_features=5000
    )

    tfidf_matrix = tfidf.fit_transform(df["text"])
    cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

    indices = pd.Series(df.index, index=df["id"])

    # Save files
    with open(os.path.join(BASE_DIR, "recommendation_model.pkl"), "wb") as f:
        pickle.dump(cosine_sim, f)

    with open(os.path.join(BASE_DIR, "video_data.pkl"), "wb") as f:
        pickle.dump(df, f)

    with open(os.path.join(BASE_DIR, "indices.pkl"), "wb") as f:
        pickle.dump(indices, f)

    with open(os.path.join(BASE_DIR, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(tfidf, f)

    print("Training completed successfully!")


if __name__ == "__main__":
    train()