# ============================================================
# recommender.py
# Content-Based Video Recommendation using Title + Description TF-IDF
# ============================================================

import os
import pickle
import numpy as np
from sklearn.metrics.pairwise import linear_kernel, cosine_similarity
from django.db.models import Case, When

from post.models import Post
from post.mlr_features import clean_post_text, fit_or_load_tfidf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "ml_models")
TFIDF_PATH = os.path.join(MODEL_DIR, "mlr_tfidf_vectorizer.pkl")


def recommend(query_or_post_id, top_n=10):
    """
    Recommend posts similar to a given post ID or text query based on Title + Description TF-IDF.
    """
    posts = list(Post.objects.select_related("author").all())
    if not posts:
        return []

    vectorizer = fit_or_load_tfidf(posts)
    post_texts = [clean_post_text(p) for p in posts]
    post_tfidf = vectorizer.transform(post_texts)

    target_idx = None
    target_vector = None

    if isinstance(query_or_post_id, int) or (isinstance(query_or_post_id, str) and query_or_post_id.isdigit()):
        post_id = int(query_or_post_id)
        for i, p in enumerate(posts):
            if p.id == post_id:
                target_idx = i
                break
        if target_idx is not None:
            target_vector = post_tfidf[target_idx]
    else:
        # String query search
        query_text = str(query_or_post_id).lower().strip()
        if query_text:
            target_vector = vectorizer.transform([query_text])

    if target_vector is None:
        return posts[:top_n]

    # Compute similarity against all posts
    sim_scores = cosine_similarity(target_vector, post_tfidf).flatten()

    # Sort indices
    sorted_indices = np.argsort(sim_scores)[::-1]

    recommended_posts = []
    for idx in sorted_indices:
        # Skip the exact same post if queried by ID
        if target_idx is not None and idx == target_idx:
            continue
        recommended_posts.append(posts[idx])
        if len(recommended_posts) >= top_n:
            break

    return recommended_posts
