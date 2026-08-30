from moderation.comment_predict import predict_comment

tests = [
    "nice video",
    "great content",
    "i like this",
    "thank you",
    "you are stupid",
    "go to hell idiot",
]

for text in tests:
    print(text)
    print(predict_comment(text))
    print("-" * 30)