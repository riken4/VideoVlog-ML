import pandas as pd

from accounts.models import CustomUser
from post.models import Post
from post.scoring import calculate_interaction_score
from sklearn.metrics.pairwise import cosine_similarity

def build_interaction_matrix():

    users = CustomUser.objects.all()
    posts = Post.objects.all()

    matrix = []

    for user in users:

        row = []

        for post in posts:

            score = calculate_interaction_score(user, post)

            row.append(score)

        matrix.append(row)

    interaction_matrix = pd.DataFrame(
        matrix,
        index=[user.id for user in users],
        columns=[post.id for post in posts]
    )

    return interaction_matrix

def calculate_user_similarity():

    interaction_matrix = build_interaction_matrix()

    similarity = cosine_similarity(interaction_matrix)

    similarity_df = pd.DataFrame(
        similarity,
        index=interaction_matrix.index,
        columns=interaction_matrix.index
    )

    return similarity_df

def get_similar_users(user_id, top_n=5):

    similarity_df = calculate_user_similarity()

    if user_id not in similarity_df.index:
        return []

    similar_users = (
        similarity_df[user_id]
        .sort_values(ascending=False)
        .iloc[1:top_n + 1]
    )

    return similar_users

def collaborative_recommend(user_id, top_n=10):

    interaction_matrix = build_interaction_matrix()

    similar_users = get_similar_users(user_id)

    if len(similar_users) == 0:
        return []

    user_scores = interaction_matrix.loc[user_id]

    watched_posts = user_scores[user_scores > 0].index.tolist()

    recommendation_scores = {}

    for similar_user_id in similar_users.index:

        similarity_score = similar_users[similar_user_id]

        similar_user_scores = interaction_matrix.loc[similar_user_id]

        for post_id, score in similar_user_scores.items():

            if post_id in watched_posts:
                continue

            if score <= 0:
                continue

            if post_id not in recommendation_scores:
                recommendation_scores[post_id] = 0

            recommendation_scores[post_id] += (
                score * similarity_score
            )

    recommended_posts = sorted(
        recommendation_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    recommended_ids = [
        post_id
        for post_id, score in recommended_posts[:top_n]
    ]

    return Post.objects.filter(
        id__in=recommended_ids
    )