# ============================================================
# mlr_features.py
# Feature extraction pipeline for MLR Recommendation Engine
# ============================================================

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from django.db.models import Count
from accounts.models import CustomUser, Follow
from post.models import Post, Like, Comment, WatchHistory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "ml_models")
os.makedirs(MODEL_DIR, exist_ok=True)

TFIDF_VECTORIZER_PATH = os.path.join(MODEL_DIR, "mlr_tfidf_vectorizer.pkl")

FEATURE_NAMES = [
    "content_score",        # TF-IDF similarity between post text & user interest profile
    "post_likes",           # log1p(total post likes)
    "post_comments",        # log1p(total post comments)
    "post_views",           # log1p(total post views)
    "user_liked",           # binary: user liked this post
    "user_commented",       # binary: user commented on this post
    "watch_duration",       # log1p(seconds user watched this post)
    "completed",            # binary: user completed watching this post
    "following_author",     # binary: user follows the post author
    "collaborative_score",  # collaborative filtering score from similar users
]


# ============================================================
# 1. TEXT EXTRACTION & TF-IDF PROCESSING
# ============================================================

def clean_post_text(post):
    """
    Extract and clean Title + Description (Content) for a post.
    """
    title = (post.title or "").strip()
    content = (post.content or "").strip()
    text = f"{title} {content}".strip()
    return text.lower() if text else "video"


def fit_or_load_tfidf(posts=None, force_refit=False):
    """
    Fit or load the TF-IDF vectorizer for post titles and descriptions.
    """
    if not force_refit and os.path.exists(TFIDF_VECTORIZER_PATH):
        try:
            with open(TFIDF_VECTORIZER_PATH, "rb") as f:
                vectorizer = pickle.load(f)
                return vectorizer
        except Exception:
            pass

    if posts is None:
        posts = list(Post.objects.all())

    texts = [clean_post_text(p) for p in posts]
    if not texts:
        texts = ["video title description"]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True
    )
    vectorizer.fit(texts)

    with open(TFIDF_VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    return vectorizer


def compute_user_content_scores(user, posts, vectorizer):
    """
    Compute content_score for all candidate posts based on user's interaction history.
    1. Builds user profile vector from posts user liked, commented, or watched.
    2. Computes cosine similarity between user profile and each candidate post vector.
    """
    if not posts:
        return {}

    post_texts = [clean_post_text(p) for p in posts]
    post_tfidf = vectorizer.transform(post_texts)

    if user is None or not user.is_authenticated:
        # Anonymous / unauthenticated: use mean TF-IDF magnitude
        norms = np.asarray(post_tfidf.mean(axis=1)).flatten()
        max_norm = norms.max() if norms.max() > 0 else 1.0
        return {p.id: float(norm / max_norm) for p, norm in zip(posts, norms)}

    # Fetch user's interactions
    liked_ids = set(Like.objects.filter(user=user).values_list("post_id", flat=True))
    commented_ids = set(Comment.objects.filter(author=user).values_list("post_id", flat=True))
    watch_records = {
        w["post_id"]: w
        for w in WatchHistory.objects.filter(user=user).values("post_id", "completed", "watch_duration")
    }

    # Weight past posts
    history_weights = {}
    for p_id in (set(watch_records.keys()) | liked_ids | commented_ids):
        weight = 0.0
        if p_id in watch_records:
            w_rec = watch_records[p_id]
            dur = float(w_rec.get("watch_duration", 0) or 0)
            # Higher watch duration directly amplifies topic importance in user profile
            weight += 1.0 + min(dur / 10.0, 5.0)
            if w_rec.get("completed"):
                weight += 3.0
        if p_id in liked_ids:
            weight += 2.0
        if p_id in commented_ids:
            weight += 2.5
        history_weights[p_id] = weight

    if not history_weights:
        # Cold start user: use general TF-IDF density
        norms = np.asarray(post_tfidf.mean(axis=1)).flatten()
        max_norm = norms.max() if norms.max() > 0 else 1.0
        return {p.id: float(norm / max_norm) for p, norm in zip(posts, norms)}

    # Build weighted user profile vector
    history_posts = list(Post.objects.filter(id__in=history_weights.keys()))
    if not history_posts:
        norms = np.asarray(post_tfidf.mean(axis=1)).flatten()
        max_norm = norms.max() if norms.max() > 0 else 1.0
        return {p.id: float(norm / max_norm) for p, norm in zip(posts, norms)}

    history_texts = [clean_post_text(p) for p in history_posts]
    history_tfidf = vectorizer.transform(history_texts)
    weights_arr = np.array([history_weights.get(p.id, 1.0) for p in history_posts]).reshape(-1, 1)

    # Weighted average representation of user preferences
    user_profile_vec = np.sum(history_tfidf.toarray() * weights_arr, axis=0, keepdims=True)
    norm = np.linalg.norm(user_profile_vec)
    if norm > 0:
        user_profile_vec = user_profile_vec / norm

    # Cosine similarity between user profile and all candidate posts
    similarities = cosine_similarity(user_profile_vec, post_tfidf).flatten()

    return {p.id: float(np.clip(sim, 0.0, 1.0)) for p, sim in zip(posts, similarities)}


# ============================================================
# 2. USER ACTIONS & COLLABORATIVE FILTERING
# ============================================================

def build_collaborative_scores(users, posts):
    """
    Calculate collaborative filtering matrix from user interaction similarities.
    """
    if not users or not posts:
        return {}

    user_ids = [u.id for u in users]
    post_ids = [p.id for p in posts]

    # Initialize interaction matrix
    interaction_df = pd.DataFrame(0.0, index=user_ids, columns=post_ids)

    # Populate watches with duration weighting
    watches = WatchHistory.objects.filter(user_id__in=user_ids, post_id__in=post_ids).values(
        "user_id", "post_id", "completed", "watch_duration"
    )
    for w in watches:
        u_id, p_id = w["user_id"], w["post_id"]
        if u_id in interaction_df.index and p_id in interaction_df.columns:
            dur = float(w.get("watch_duration", 0) or 0)
            dur_score = 1.0 + min(dur / 10.0, 5.0)
            if w.get("completed"):
                dur_score += 4.0
            interaction_df.loc[u_id, p_id] += dur_score

    # Populate likes
    likes = Like.objects.filter(user_id__in=user_ids, post_id__in=post_ids).values("user_id", "post_id")
    for l in likes:
        u_id, p_id = l["user_id"], l["post_id"]
        if u_id in interaction_df.index and p_id in interaction_df.columns:
            interaction_df.loc[u_id, p_id] += 3.0

    # Populate comments
    comments = Comment.objects.filter(author_id__in=user_ids, post_id__in=post_ids).values("author_id", "post_id")
    for c in comments:
        u_id, p_id = c["author_id"], c["post_id"]
        if u_id in interaction_df.index and p_id in interaction_df.columns:
            interaction_df.loc[u_id, p_id] += 4.0

    # Populate follow bonuses
    follows = Follow.objects.filter(follower_id__in=user_ids).values("follower_id", "following_id")
    follow_map = {(f["follower_id"], f["following_id"]) for f in follows}
    for p in posts:
        for u_id in user_ids:
            if (u_id, p.author_id) in follow_map:
                interaction_df.loc[u_id, p.id] += 2.0

    if interaction_df.values.max() == 0:
        return {u_id: {} for u_id in user_ids}

    # Cosine similarity between users
    user_sim_matrix = cosine_similarity(interaction_df.values)
    user_sim_df = pd.DataFrame(user_sim_matrix, index=user_ids, columns=user_ids)

    collaborative_scores = {}
    for u_id in user_ids:
        # Top 5 most similar other users
        sim_series = user_sim_df.loc[u_id].drop(index=u_id, errors="ignore")
        top_similar = sim_series.sort_values(ascending=False).head(5)
        top_similar = top_similar[top_similar > 0]

        scores = {}
        if not top_similar.empty:
            similar_matrix = interaction_df.loc[top_similar.index]
            # Weighted interaction scores
            weighted_scores = np.dot(top_similar.values, similar_matrix.values)
            sum_sim = top_similar.sum()
            if sum_sim > 0:
                weighted_scores /= sum_sim

            for p_id, score in zip(post_ids, weighted_scores):
                if score > 0:
                    scores[p_id] = float(score)

        collaborative_scores[u_id] = scores

    return collaborative_scores


# ============================================================
# 3. MLR FEATURE VECTOR GENERATION
# ============================================================

def build_features_for_user(user, posts, vectorizer=None):
    """
    Build MLR feature DataFrame for candidate posts given a target user.
    """
    if not posts:
        return pd.DataFrame(columns=FEATURE_NAMES)

    if vectorizer is None:
        vectorizer = fit_or_load_tfidf(posts)

    # 1. TF-IDF Content Scores
    content_scores = compute_user_content_scores(user, posts, vectorizer)

    # 2. Bulk load video popularity signals
    post_ids = [p.id for p in posts]
    view_counts = dict(
        WatchHistory.objects.filter(post_id__in=post_ids)
        .values("post_id")
        .annotate(v_count=Count("id"))
        .values_list("post_id", "v_count")
    )
    like_counts = dict(
        Like.objects.filter(post_id__in=post_ids)
        .values("post_id")
        .annotate(l_count=Count("id"))
        .values_list("post_id", "l_count")
    )
    comment_counts = dict(
        Comment.objects.filter(post_id__in=post_ids)
        .values("post_id")
        .annotate(c_count=Count("id"))
        .values_list("post_id", "c_count")
    )

    # 3. Bulk load user-specific actions
    if user and user.is_authenticated:
        user_liked_set = set(
            Like.objects.filter(user=user, post_id__in=post_ids).values_list("post_id", flat=True)
        )
        user_commented_set = set(
            Comment.objects.filter(author=user, post_id__in=post_ids).values_list("post_id", flat=True)
        )
        user_watches = {
            w["post_id"]: w
            for w in WatchHistory.objects.filter(user=user, post_id__in=post_ids).values(
                "post_id", "watch_duration", "completed"
            )
        }
        following_author_ids = set(
            Follow.objects.filter(follower=user).values_list("following_id", flat=True)
        )
        collab_map = build_collaborative_scores([user], posts).get(user.id, {})
    else:
        user_liked_set = set()
        user_commented_set = set()
        user_watches = {}
        following_author_ids = set()
        collab_map = {}

    rows = []
    for post in posts:
        c_score = content_scores.get(post.id, 0.0)
        p_likes = float(np.log1p(like_counts.get(post.id, 0)))
        p_comments = float(np.log1p(comment_counts.get(post.id, 0)))
        p_views = float(np.log1p(view_counts.get(post.id, 0)))

        u_liked = 1.0 if post.id in user_liked_set else 0.0
        u_commented = 1.0 if post.id in user_commented_set else 0.0

        watch_info = user_watches.get(post.id)
        w_duration = float(np.log1p(watch_info["watch_duration"])) if watch_info else 0.0
        w_completed = 1.0 if (watch_info and watch_info.get("completed")) else 0.0

        f_author = 1.0 if post.author_id in following_author_ids else 0.0
        collab_score = float(collab_map.get(post.id, 0.0))

        rows.append({
            "content_score": c_score,
            "post_likes": p_likes,
            "post_comments": p_comments,
            "post_views": p_views,
            "user_liked": u_liked,
            "user_commented": u_commented,
            "watch_duration": w_duration,
            "completed": w_completed,
            "following_author": f_author,
            "collaborative_score": collab_score,
        })

    return pd.DataFrame(rows, columns=FEATURE_NAMES)