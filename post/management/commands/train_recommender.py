from django.core.management.base import BaseCommand
from post.train_mlr import train


class Command(BaseCommand):
    help = "Train the MLR recommendation model and TF-IDF pipeline"

    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.SUCCESS(
                "Starting recommendation training..."
            )
        )

        train()

        self.stdout.write(
            self.style.SUCCESS(
                "MLR Recommendation training completed successfully!"
            )
        )