import os
import pickle

from django.db.models import Case, When

from post.models import Post

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

cosine_sim = pickle.load(
    open(os.path.join(BASE_DIR, "recommendation_model.pkl"), "rb")
)

video_data = pickle.load(
    open(os.path.join(BASE_DIR, "video_data.pkl"), "rb")
)

indices = pickle.load(
    open(os.path.join(BASE_DIR, "indices.pkl"), "rb")
)


def recommend(post_id, top_n=10):

    if post_id not in indices:
        return []

    idx = indices[post_id]

    similarity_scores = list(enumerate(cosine_sim[idx]))

    similarity_scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    similarity_scores = similarity_scores[1:top_n + 1]

    recommended_ids = [
        int(video_data.iloc[i[0]]["id"])
        for i in similarity_scores
    ]

    preserved_order = Case(
        *[
            When(id=pk, then=position)
            for position, pk in enumerate(recommended_ids)
        ]
    )

    posts = Post.objects.filter(
        id__in=recommended_ids
    ).select_related(
        "author"
    ).order_by(
        preserved_order
    )

    return posts

