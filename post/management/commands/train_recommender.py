from django.core.management.base import BaseCommand

from post.train_model import train


class Command(BaseCommand):

    help = "Train the recommendation model"

    def handle(self, *args, **kwargs):

        self.stdout.write(
            self.style.SUCCESS(
                "Starting recommendation training..."
            )
        )

        train()

        self.stdout.write(
            self.style.SUCCESS(
                "Training completed successfully!"
            )
        )